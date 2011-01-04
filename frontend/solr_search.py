# Copyright 2009 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
low-level routines for querying SOLR and processing the results.
Please don't call this directly-- instead call search.py
"""

import datetime
import logging
import re
import time
import traceback
import urllib

from django.utils import simplejson
from versioned_memcache import memcache
from google.appengine.api import urlfetch
from copy import deepcopy

import api

import geocode
import ical_filter
import models
import modelutils
import posting
import private_keys
import boosts
import searchresult

RESULT_CACHE_TIME = 900 # seconds
RESULT_CACHE_KEY = 'searchresult:'

# Date format pattern used in date ranges.
DATE_FORMAT_PATTERN = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')

# max number of results to ask from SOLR (for latency-- and correctness?)
MAX_RESULTS = 1000

MILES_PER_DEG = 69
DEFAULT_VOL_DIST = 75

def default_boosts(args):
  boost = ""
  
  if api.PARAM_Q in args and args[api.PARAM_Q] == "":    
    
    # boosting vetted categories
    boost += '&bq=categories:vetted^15'    
    # big penalty for events starting in the far future
    boost += '+eventrangestart:[*+TO+NOW%2B6MONTHS]^15'    
    # big boost for events starting in the near future
    boost += '+eventrangestart:[NOW+TO+NOW%2B1MONTHS]^10'    
    # slight penalty for events started recently
    boost += '+=eventrangestart:[NOW+TO+*]^5'    
    # modest penalty for events started long ago
    boost += '+eventrangestart:[NOW-6MONTHS+TO+*]^7'    
    # modest penalty for events ending in the far future
    boost += '+eventrangeend:[*+TO+NOW%2B6MONTHS]^7'     
    # big boost for events ending in the near future
    boost += '+eventrangeend:[NOW+TO+NOW%2B1MONTHS]^10'    
    # boost short events
    boost += '+eventduration:[1+TO+10]^10'
  
  return boost  

def add_range_filter(field, min_val, max_val):
  """ Convert colons in the field name and build a range specifier
  in SOLR query syntax"""
  # TODO: Deal with escapification
  result = ' +AND+ '
  result += field
  result += ':[' + str(min_val) +' TO ' + str(max_val) + ']'
  return result

def rewrite_query(query_str, api_key = None):
  """ Rewrites the query string from an easy to type and understand format
  into a Solr-readable format"""
  # Lower-case everything and make boolean operators upper-case, so they
  # are recognized by SOLR.
  # TODO: Don't lowercase field names.
  rewritten_query = query_str.lower()
  rewritten_query = rewritten_query.replace(' or ', ' OR ')
  rewritten_query = rewritten_query.replace(' and ', ' AND ')
  rewritten_query = rewritten_query.replace(' to ', ' TO ')
  
  # 2011-01-17T00:00:00.000Z is a valid date string
  # but 2011-01-17t00:00:00.000z is not
  def reupcase(match_obj):
    return match_obj.group(0).upper()

  rewritten_query = re.sub(r'[0-9]t[0-9]', reupcase, rewritten_query)
  rewritten_query = re.sub(r'[0-9]z', reupcase, rewritten_query)
  if rewritten_query.find('meetup') < 0 and api_key and api_key in private_keys.MEETUP_EXCLUDERS:
    logging.info('solr_search.rewrite_query api key %s excludes meetup' % api_key)
    rewritten_query = '(' + rewritten_query + ') AND -feed_providername:meetup'

  # Replace the category filter shortcut with its proper name.
  rewritten_query = rewritten_query.replace('category:', 'categories:')

  return rewritten_query

def form_solr_query(args):
  solr_query = ''

  api_key = None
  if api.PARAM_KEY in args:
    api_key = args[api.PARAM_KEY]
    logging.info('api_key = %s' % api_key)

  # args fix up
  if api.PARAM_START not in args:
    args[api.PARAM_START] = 1

  if api.PARAM_SORT not in args:
    args[api.PARAM_SORT] = "r"

  # Generate geo search parameters
  # TODO: formalize these constants
  # this is near the middle of the continental US 
  lat = '37'
  lng = '-95'
  max_dist = 1500
  if api.PARAM_LAT in args and api.PARAM_LNG in args and \
     (args[api.PARAM_LAT] != "" and args[api.PARAM_LNG] != ""):
    lat = args[api.PARAM_LAT]
    lng = args[api.PARAM_LNG]
    if api.PARAM_VOL_DIST not in args or args[api.PARAM_VOL_DIST] == "":
      args[api.PARAM_VOL_DIST] = DEFAULT_VOL_DIST
    max_dist = args[api.PARAM_VOL_DIST] = int(str(args[api.PARAM_VOL_DIST]))
    if args[api.PARAM_VOL_DIST] < 1:
      args[api.PARAM_VOL_DIST] = DEFAULT_VOL_DIST
    max_dist = float(args[api.PARAM_VOL_DIST])
  
  boost_params = default_boosts(args);
  geo_params = '{!spatial lat=' + str(lat) + ' long=' + str(lng) + ' radius=' + str(max_dist) + ' boost=recip(dist(geo_distance),1,1000,1000)^1000}'   

  # keyword
  query_is_empty = False
  if (api.PARAM_Q in args and args[api.PARAM_Q] != "") or (api.PARAM_CATEGORY in args and args[api.PARAM_CATEGORY] != "all") or (api.PARAM_SOURCE in args and args[api.PARAM_SOURCE] != "all"):
    query_boosts = boosts.query_time_boosts(args)
    if query_boosts:
      solr_query = query_boosts    
    else:
      solr_query += rewrite_query(args[api.PARAM_Q])
  else:
    # Query is empty, search for anything at all.
    solr_query += rewrite_query('*:*', api_key)
    query_is_empty = True

  # date range
  if api.PARAM_VOL_STARTDATE in args and args[api.PARAM_VOL_STARTDATE] != "":
    start_date = datetime.datetime.today()
    try:
      start_date = datetime.datetime.strptime(
                     args[api.PARAM_VOL_STARTDATE].strip(), "%Y-%m-%d")
    except:
      logging.debug('solr_search.form_solr_query malformed start date: %s' %
                    args[api.PARAM_VOL_STARTDATE])
    end_date = None
    if api.PARAM_VOL_ENDDATE in args and args[api.PARAM_VOL_ENDDATE] != "":
      try:
        end_date = datetime.datetime.strptime(
                       args[api.PARAM_VOL_ENDDATE].strip(), "%Y-%m-%d")
      except:
        logging.debug('solr_search.form_solr_query malformed end date: %s' %
                       args[api.PARAM_VOL_ENDDATE])
    if not end_date:
      end_date = start_date
    start_datetime_str = start_date.strftime("%Y-%m-%dT00:00:00.000Z")
    end_datetime_str = end_date.strftime("%Y-%m-%dT23:59:59.999Z")
    if (api.PARAM_VOL_INCLUSIVEDATES in args and
       args[api.PARAM_VOL_INCLUSIVEDATES] == 'true'):
      solr_query += add_range_filter("eventrangestart", start_datetime_str, '*')
      solr_query += add_range_filter("eventrangeend", '*', end_datetime_str)
    else:
      solr_query += add_range_filter("eventrangestart", '*', end_datetime_str)
      solr_query += add_range_filter("eventrangeend", start_datetime_str, '*')

  # geo params go in first
  solr_query = geo_params + solr_query
  solr_query = urllib.quote_plus(solr_query)
  
  # Type
  if api.PARAM_TYPE in args:
    if args[api.PARAM_TYPE] == "self_directed":
      solr_query += " AND self_directed:true"    
    elif args[api.PARAM_TYPE] == "virtual":
      solr_query += " AND virtual:true"
  
  added_categories = False
  # Category
  if api.PARAM_CATEGORY in args and args[api.PARAM_CATEGORY] != "all":
    solr_query += "categories:(" + args[api.PARAM_CATEGORY] + ")"
    added_categories = True
    
  # Source
  if api.PARAM_SOURCE in args and args[api.PARAM_SOURCE] != "all":
    if added_categories:
      solr_query += "+AND+"
    solr_query += "feed_providername:" + args[api.PARAM_SOURCE]
      
  # for ad campaigns
  if api.PARAM_CAMPAIGN_ID in args:
    # we need to exclude the opted out opportunities
    # they can be tagged as opt_out_all_campaigns
    # or opt_out_campaign_XXX where XXX is the campaign ID.
    exclusion = '!categories:%s !categories:%s' % (
      'optout_all_campaigns',
      'optout_campaign_' + args[api.PARAM_CAMPAIGN_ID]
    )
    # TODO: campaign_ids are per-campaign, but opportunities
    # might prefer to opt out of an entire sponsor.
    # should probably add a 'sponsor_id' to the spreadsheet,
    # and have optout_sponsor_XXX as well.
    solr_query += exclusion

  # set the solr instance we need to use if not given as an arg
  if api.PARAM_BACKEND_URL not in args:
    try:
      args[api.PARAM_BACKEND_URL] = private_keys.DEFAULT_BACKEND_URL_SOLR
    except:
      raise NameError("error reading private_keys.DEFAULT_BACKEND_URL_SOLR-- "+
                     "please install correct private_keys.py file")

  # field list
  solr_query += '&fl='
  if api.PARAM_OUTPUT not in args:
    solr_query += api.DEFAULT_OUTPUT_FIELDS
  else:
    if args[api.PARAM_OUTPUT] in api.FIELDS_BY_OUTPUT_TYPE:
      solr_query += api.FIELDS_BY_OUTPUT_TYPE[args[api.PARAM_OUTPUT]]
    else:
      solr_query += '*' 

  #facet counts
  if api.PARAM_FACET in args:
      solr_query += '&facet=' + args[api.PARAM_FACET]
      if api.PARAM_FACET_LIMIT in args:
          solr_query += '&facet.limit=' + args[api.PARAM_FACET_LIMIT]
      #if api.PARAM_FACET_MINCNT in args:
      #    solr_query += '&facet.mincount=' + args[api.PARAM_FACET_MINCNT]
      facet_field = 0
      while True:
          facet_field_str = api.PARAM_FACET_FIELD + str(facet_field)
          facet_field = facet_field + 1
          if facet_field_str in args:
              solr_query += '&facet.field=' + args[facet_field_str]
          else:
              break
          
  return solr_query + boost_params

def parseLatLng(val):
  """ return precisely zero if a lat|lng value is very nearly zero."""
  try:
    if val is None or val == "":
      return 0.0
    floatval = float(val)
    if floatval > -0.01 and floatval < 0.01:
      return 0.0
    return floatval
  except:
    return 0.0

# note: many of the XSS and injection-attack defenses are unnecessary
# given that the callers are also protecting us, but I figure better
# safe than sorry, and defense-in-depth.
def search(args, dumping = False):
  """run a SOLR search."""
  def have_valid_query(args):
    """ make sure we were given a value for at least one of these arguments """
    valid_query = False
    api_list = [api.PARAM_Q,
                api.PARAM_TIMEPERIOD_START,
                api.PARAM_TIMEPERIOD_END,
                api.PARAM_VOL_LOC,
                'virtual',
                api.PARAM_VOL_STARTDATE,
                api.PARAM_VOL_ENDDATE,
                api.PARAM_VOL_DURATION,
                api.PARAM_VOL_PROVIDER,
                api.PARAM_VOL_STARTDAYOFWEEK]

    for param in api_list:
      if param in args and args[param]:
        if param == api.PARAM_VOL_LOC:
          # vol_loc must render a lat, long pair
          if (args[param] != "virtual" and
              not args[api.PARAM_LAT] or 
              parseLatLng(args[api.PARAM_LAT]) == 0 or 
              not args[api.PARAM_LNG] or 
              parseLatLng(args[api.PARAM_LNG]) == 0):
            continue
        valid_query = True
        break
      
    return valid_query

  if api.PARAM_SOLR_PATH in args and args[api.PARAM_SOLR_PATH]:
    solr_query = form_solr_query(args, args[api.PARAM_SOLR_PATH])
  else:
    solr_query = form_solr_query(args)

  query_url = args[api.PARAM_BACKEND_URL]
  if query_url.find("?") < 0:
    # yeah yeah, should really parse the URL
    query_url += "?"

  # Return results in JSON format
  # TODO: return in TSV format for fastest possible parsing, i.e. split("\t") 
  query_url += "&wt=json"
  
  # Sort
  logging.info(args[api.PARAM_SORT]);
  if api.PARAM_SORT in args:
    query_url += "&sort=" + args[api.PARAM_SORT] + "%20desc"

  # limit to opps which have not expired yet
  # [expires:NOW TO *] means "expires prior to today"
  query_url += "&fq=expires:[NOW-3DAYS%20TO%20*]"

  #num_to_fetch = int(args[api.PARAM_NUM]) + 1
  num_to_fetch = 50
  query_url += "&rows=" + str(num_to_fetch)
  query_url += "&start=" + str(int(args[api.PARAM_START]) - 1)

  query_url += "&q=" + solr_query
  if not have_valid_query(args):
    # no query + no location = no results
    result_set = searchresult.SearchResultSet(urllib.unquote(query_url),
                                            query_url,
                                            [])
    logging.debug("SOLR not called: no query given")
    result_set.query_url = query_url
    result_set.args = args
    result_set.num_results = 0
    result_set.estimated_results = 0
    result_set.fetch_time = 0
    result_set.parse_time = 0
    return result_set

  logging.info("calling SOLR: "+query_url)
  results = query(query_url, args, False, dumping)
  logging.info("SOLR call done: "+str(len(results.results))+
                " results, fetched in "+str(results.fetch_time)+" secs,"+
                " parsed in "+str(results.parse_time)+" secs.")

  # Base doesn't implement day-of-week filtering
  if (api.PARAM_VOL_STARTDAYOFWEEK in args and
      args[api.PARAM_VOL_STARTDAYOFWEEK] != ""):
    startday = args[api.PARAM_VOL_STARTDAYOFWEEK]
    for i, res in enumerate(results):
      dow = str(res.startdate.strftime("%w"))
      if startday.find(dow) < 0:
        del results[i]

  return results


def query(query_url, args, cache, dumping = False):
  """run the actual SOLR query (no filtering or sorting)."""
  logging.debug("Query URL: " + query_url + '&debugQuery=on')
  result_set = searchresult.SearchResultSet(urllib.unquote(query_url),
                                            query_url,
                                            [])

  result_set.query_url = query_url
  result_set.args = args
  result_set.fetch_time = 0
  result_set.parse_time = 0
  
  fetch_start = time.time()
  status_code = 999
  try:
    fetch_result = urlfetch.fetch(query_url,
                   deadline = api.CONST_MAX_FETCH_DEADLINE)
    status_code = fetch_result.status_code
  except:
    # can get a response too large error here
    if status_code == 999:
      logging.info('solr_search.query error')
    else:
      logging.info('solr_search.query responded %s' % str(status_code))

  fetch_end = time.time()
  result_set.fetch_time = fetch_end - fetch_start
  if status_code != 200:
    return result_set
  result_content = fetch_result.content

  parse_start = time.time()
  # undo comma encoding -- see datahub/footprint_lib.py
  result_content = re.sub(r';;', ',', result_content)
  result = simplejson.loads(result_content)
  
  #facet_counts
  if "facet_counts" in result:
    facet_counts = result["facet_counts"]["facet_fields"]
    result_set.facet_counts = deepcopy(facet_counts)
  else:
      result_set.facet_counts = None

  doc_list = result["response"]["docs"]

  for i, entry in enumerate(doc_list):
    if not "detailurl" in entry:
      # URL is required 
      latstr = entry["latitude"]
      longstr = entry["longitude"]
      if latstr and longstr and latstr != "" and longstr != "":
        entry["detailurl"] = \
          "http://maps.google.com/maps?q=" + str(latstr) + "," + str(longstr)
      else:
        logging.debug('solr_search.query skipping SOLR record' +
                      ' %d: detailurl is missing...' % i)
        continue

    url = entry["detailurl"]
    # ID is the 'stable id' of the item generated by base.
    # Note that this is not the base url expressed as the Atom id element.
    item_id = entry["id"]
    # Base URL is the url of the item in base. For Solr we just use the ID hash
    base_url = item_id
    snippet = entry.get('abstract', '')
    title = entry.get('title', '')
    location = entry.get('location_string', '')

    categories = entry.get('categories', '')
    if type(categories).__name__ != 'list':
      try:
        categories = categories.split(',')
      except:
        categories = []
    
    org_name = entry.get('org_name', '')
    if re.search(r'[^a-z]acorn[^a-z]', " "+org_name+" ", re.IGNORECASE):
      logging.debug('solr_search.query skipping: ACORN in org_name')
      continue
    latstr = entry["latitude"]
    longstr = entry["longitude"]
    virtual = (entry.get('virtual') == 'true' or 
               not latstr and not longstr or
               latstr and longstr and latstr == '0.0' and longstr == '0.0')
    self_directed = entry.get("self_directed")
    volunteers_needed = entry.get("volunteersneeded")
    res = searchresult.SearchResult(url, title, snippet, location, item_id,
                                    base_url, volunteers_needed, virtual,
                                    self_directed, categories, org_name)

    # TODO: escape?
    res.provider = entry["feed_providername"]
    if (res.provider == "myproj_servegov" and
        re.search(r'[^a-z]acorn[^a-z]', " "+result_content+" ", re.IGNORECASE)):
      # per-provider rule because case-insensitivity
      logging.info('solr_search.query skipping: ACORN in for myproj_servegov')
      continue

    res.orig_idx = i+1
    res.latlong = ""
    if latstr and longstr and latstr != "" and longstr != "":
      if ( not dumping and
           api.PARAM_VOL_DIST in args and args[api.PARAM_VOL_DIST] != "" and
           api.PARAM_LAT in args and args[api.PARAM_LAT] != "" and
           api.PARAM_LNG in args and args[api.PARAM_LNG] != ""
         ):
        # beyond distance from requested?
        try:
          max_vol_dist = float(args[api.PARAM_VOL_DIST])
          vol_lat = float(args[api.PARAM_LAT])
          vol_lng = float(args[api.PARAM_LNG])
          result_lat = float(latstr)
          result_lng = float(longstr)
          miles_to_opp = float(entry["geo_distance"])
          if miles_to_opp > max_vol_dist:
            logging.info("skipping SOLR record %d: too far (%d > %d)" % 
              (i, miles_to_opp, max_vol_dist))
            continue
        except:
          logging.info("could not calc %s max distance [%s,%s] to [%s,%s]" %
            (args[api.PARAM_VOL_DIST], args[api.PARAM_LAT], args[api.PARAM_LNG], 
              latstr, longstr))

      res.latlong = str(latstr) + "," + str(longstr)

    # TODO: remove-- working around a DB bug where all latlongs are the same
    if not dumping and "geocode_responses" in args:
      res.latlong = geocode.geocode(location,
            args["geocode_responses"]!="nocache" )

    # res.event_date_range follows one of these two formats:
    #     <start_date>T<start_time> <end_date>T<end_time>
    #     <date>T<time>
    res.event_date_range = entry["event_date_range"]
    res.startdate = datetime.datetime.strptime("2000-01-01", "%Y-%m-%d")
    res.enddate = datetime.datetime.strptime("2038-01-01", "%Y-%m-%d")
    if not dumping and res.event_date_range:
      match = DATE_FORMAT_PATTERN.findall(res.event_date_range)
      if not match:
        logging.debug('solr_search.query skipping record' +
                        ' %d: bad date range: %s for %s' % 
                        (i, res.event_date_range, url))
        continue
      else:
        # first match is start date/time
        startdate = datetime.datetime.strptime(match[0], '%Y-%m-%dT%H:%M:%S')
        # last match is either end date/time or start/date time
        enddate = datetime.datetime.strptime(match[-1], '%Y-%m-%dT%H:%M:%S')
        # protect against absurd dates
        if startdate > res.startdate:
          res.startdate = startdate
        if enddate < res.enddate:
          res.enddate = enddate

    openended = "openended" in entry and entry["openended"]
    if openended and "ical_recurrence" in entry:
      ical_recurrence = entry["ical_recurrence"]
      query_startdate = args[api.PARAM_VOL_STARTDATE] if api.PARAM_VOL_STARTDATE in args else None
      query_enddate = args[api.PARAM_VOL_ENDDATE] if api.PARAM_VOL_ENDDATE in args else None
      if not ical_filter.match(ical_recurrence, query_startdate, query_enddate):
        logging.warning("skipping SOLR record %d: failed the iCal filter" % i)
        continue

    # posting.py currently has an authoritative list of fields in "argnames"
    # that are available to submitted events which may later appear in GBase
    # so with a few exceptions we want those same fields to become
    # attributes of our result object
    except_names = ["title", "description"]
    for name in posting.argnames:
      if name not in except_names and name.lower() in entry:
        # Solr field names are all lowercase.
        # TODO: fix list in posting.py so it matches solr's fieldnames.
        setattr(res, name, entry[name.lower()])

    result_set.results.append(res)
    if cache and res.item_id:
      key = RESULT_CACHE_KEY + res.item_id
      memcache.set(key, res, time=RESULT_CACHE_TIME)

  result_set.num_results = len(result_set.results)

  result_set.estimated_results = int(result["response"]["numFound"])
  parse_end = time.time()
  result_set.parse_time = parse_end - parse_start
  return result_set

def get_from_ids(ids):
  """Return a result set containing multiple results for multiple ids.

  Args:
    ids: List of stable IDs of volunteer opportunities.

  Returns:
    searchresult.SearchResultSet with just the entries in ids.
  """

  result_set = searchresult.SearchResultSet('', '', [])

  # First get all that we can from memcache
  results = {}
  try:
    # get_multi returns a dictionary of the keys and values that were present
    # in memcache. Even with the key_prefix specified, that key_prefix won't
    # be on the keys in the returned dictionary.
    hits = memcache.get_multi(ids, RESULT_CACHE_KEY)
  except:
    # TODO(mblain): Scope to only 'memcache down' exception.
    logging.exception('get_from_ids: ignoring busted memcache. stack: %s',
                      ''.join(traceback.format_stack()))

  temp_results_dict = {}

  for key in hits:
    result = hits[key]
    temp_results_dict[result.item_id] = result

  # OK, we've collected what we can from memcache. Now look up the rest.
  # Find the Google Base url from the datastore, then look that up in base.
  missing_ids = []
  for item_id in ids:
    if not item_id in hits:
      missing_ids.append(item_id)

  datastore_results = modelutils.get_by_ids(models.VolunteerOpportunity,
      missing_ids)

  datastore_missing_ids = []
  for item_id in ids:
    if not item_id in datastore_results:
      datastore_missing_ids.append(item_id)
  if datastore_missing_ids:
    logging.warning('solr_search.get_from_ids Could not find entry in' +
                    ' datastore for ids: %s' % datastore_missing_ids)

  # Bogus args for search. TODO: Remove these, why are they needed above?
  args = {}
  args[api.PARAM_VOL_STARTDATE] = (datetime.date.today() +
                       datetime.timedelta(days=1)).strftime("%Y-%m-%d")
  datetm = time.strptime(args[api.PARAM_VOL_STARTDATE], "%Y-%m-%d")
  args[api.PARAM_VOL_ENDDATE] = (datetime.date(datetm.tm_year, datetm.tm_mon,
      datetm.tm_mday) + datetime.timedelta(days=60))

  # TODO(mblain): Figure out how to pull in multiple base entries in one call.
  for (item_id, volunteer_opportunity_entity) in datastore_results.iteritems():
    if not volunteer_opportunity_entity.base_url:
      logging.warning('solr_search.get_from_ids no base_url in datastore ' +
                      'for id: %s' % item_id)
      continue
    logging.debug("Datastore Entry: " + volunteer_opportunity_entity.base_url) ##
    try:
      query_url = private_keys.DEFAULT_BACKEND_URL_SOLR + \
          '?wt=json&q=id:' + volunteer_opportunity_entity.base_url
    except:
      raise NameError("error reading private_keys.DEFAULT_BACKEND_URL_SOLR-- "+
                      "please install correct private_keys.py file")
    temp_results = query(query_url, args, True)
    if not temp_results.results:
      # The base URL may have changed from under us. Oh well.
      # TODO: "info" is not defined so this logging line breaks.
      # logging.warning('Did not get results from base. id: %s base_url: %s '
      #                 'Last update: %s Previous failure: %s' %
      #                 (id, info.base_url, info.last_base_url_update,
      #                  info.last_base_url_update_failure))
      volunteer_opportunity_entity.base_url_failure_count += 1
      volunteer_opportunity_entity.last_base_url_update_failure = \
          datetime.datetime.now()
      volunteer_opportunity_entity.put()
      continue
    if temp_results.results[0].item_id != item_id:
      logging.error('solr_search.get_from_ids First result not expected result.'
                    ' Expected: %s Found: %s. len(results): %s' %
                    (item_id, temp_results.results[0].item_id, len(results)))
      # Not sure if we should touch the VolunteerOpportunity or not.
      continue
    temp_result = temp_results.results[0]
    temp_results_dict[temp_result.item_id] = temp_result

  # Our temp result set should now contain both stuff that was looked up from
  # cache as well as stuff that got fetched directly from Base.  Now order
  # the events according to the original list of id's.
  
  # First reverse the list of id's, so events come out in the right order
  # after being prepended to the events list.
  ids.reverse()
  for id in ids:
    result = temp_results_dict.get(id, None)
    if result:
      result_set.results.insert(0, result)

  return result_set


