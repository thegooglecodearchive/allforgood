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

import api

import geocode
import models
import modelutils
import posting
import private_keys
import searchresult

RESULT_CACHE_TIME = 900 # seconds
RESULT_CACHE_KEY = 'searchresult:'

# Date format pattern used in date ranges.
DATE_FORMAT_PATTERN = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')

# max number of results to ask from SOLR (for latency-- and correctness?)
MAX_RESULTS = 1000

MILES_PER_DEG = 69

def build_function_query(base_lat, base_long, max_dist, get_random_results):
  """Builds a function query for Solr scoring and ranking.
  
     For more info: http://wiki.apache.org/solr/FunctionQuery
     Results are sorted by score. The final score is computed as follows:
     final_score = relevancy + geo_score + duration_score"""
  
  # FQs don't support subtraction, so we need to add negative numbers.
  neg_lat = '-' + base_lat
  if neg_lat.startswith('--'):
    neg_lat = neg_lat[2:]
  neg_long = '-' + base_long
  if neg_long.startswith('--'):
    neg_long = neg_long[2:]

  negative_max_dist_squared = str(max_dist * (-max_dist))

  # Geo scoring - Favors nearby results
  # Equals 1 at the base location and drops to 0 at max_dist miles away.
  # Formula: (max_dist^2 - dist^2) / max_dist^2
  distance_squared ='sum(' \
                      'product(' \
                        'sum(' + neg_lat + ', latitude),' \
                        'sum(' + neg_lat + ', latitude)' \
                      '),' \
                      'product(' \
                        'sum(' + neg_long + ', longitude),' \
                        'sum(' + neg_long + ', longitude)' \
                      ')' \
                    ')'

  geo_score_str = 'div(' \
                    'sum(' + \
                      negative_max_dist_squared + ',' + \
                      distance_squared + \
                    '),' + \
                    negative_max_dist_squared + \
                  ')'
  
  # Duration scoring - Favors short events
  # Equals 1 for 1-day events (duration 0), and decays exponentially 
  # with a half life of 10 days
  duration_score_str = 'div(1,log(sum(10,eventduration)))'
  
  # Now set the weights for each score (relevance has a hardcoded weight of 1)
  # Relevancy isn't really applicable to volunteer opportunity, so we set
  # other weights way higher. Location is more important than duration, hence
  # the 6:3 ratio.
  geo_weight = '6'
  duration_weight = '3'
  geo_score_str = 'product(' + geo_weight + ',' + geo_score_str + ')'
  duration_score_str = 'product(' + duration_weight + ',' + \
                       duration_score_str + ')'
  score_str = 'sum(' + geo_score_str + ',' + duration_score_str + ')'

  # Add the salt to the final score to make results more varied per page.
  if get_random_results:
    # If the query is empty, we assume the user wants to browse, so we up the
    # random salt 10x.
    score_str = 'sum(' + score_str + ',product(10, randomsalt))'
  else:
    score_str = 'sum(' + score_str + ',randomsalt)'
  function_query = ' AND _val_:"' + score_str
  
  function_query += '"'
  return function_query

def add_range_filter(field, min_val, max_val):
  """ Convert colons in the field name and build a range specifier
  in SOLR query syntax"""
  # TODO: Deal with escapification
  result = ' AND '
  result += field
  result += ':[' + str(min_val) +' TO ' + str(max_val) + ']'
  return result

def rewrite_query(query_str):
  """ Rewrites the query string from an easy to type and understand format
  into a Solr-readable format"""
  # Lower-case everything and make boolean operators upper-case, so they
  # are recognized by SOLR.
  # TODO: Don't lowercase field names.
  rewritten_query = query_str.lower()
  rewritten_query = rewritten_query.replace(' or ', ' OR ')
  rewritten_query = rewritten_query.replace(' and ', ' AND ')

  # Replace the category filter shortcut with its proper name.
  rewritten_query = rewritten_query.replace('category:', 'categories:')

  return rewritten_query

def form_solr_query(args):
  """ensure args[] has all correct and well-formed members and
  return a solr query string."""

  logging.debug("form_solr_query: "+str(args))
  solr_query = ""
  query_is_empty = False
  if api.PARAM_Q in args and args[api.PARAM_Q] != "":
    solr_query += rewrite_query(args[api.PARAM_Q])
  else:
    # Query is empty, search for anything at all.
    solr_query += "*:*"
    query_is_empty = True

  logging.info("solr_query: %s" % solr_query)

  if api.PARAM_VOL_STARTDATE in args and args[api.PARAM_VOL_STARTDATE] != "":
    start_date = datetime.datetime.today()
    try:
      start_date = datetime.datetime.strptime(
                     args[api.PARAM_VOL_STARTDATE].strip(), "%Y-%m-%d")
    except:
      logging.error("malformed start date: %s" % args[api.PARAM_VOL_STARTDATE])
    end_date = None
    if api.PARAM_VOL_ENDDATE in args and args[api.PARAM_VOL_ENDDATE] != "":
      try:
        end_date = datetime.datetime.strptime(
                       args[api.PARAM_VOL_ENDDATE].strip(), "%Y-%m-%d")
      except:
        logging.error("malformed end date: %s" % args[api.PARAM_VOL_ENDDATE])
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

  if api.PARAM_VOL_PROVIDER in args and args[api.PARAM_VOL_PROVIDER] != "":
    if re.match(r'[a-zA-Z0-9:/_. -]+', args[api.PARAM_VOL_PROVIDER]):
      solr_query += " AND feed_providername:" + \
                      args[api.PARAM_VOL_PROVIDER]
    else:
      # illegal providername
      # TODO: throw 500
      logging.error("illegal providername: " + args[api.PARAM_VOL_PROVIDER])
  # TODO: injection attack on sort
  if api.PARAM_SORT not in args:
    args[api.PARAM_SORT] = "r"

  # Generate geo search parameters
  if api.PARAM_LAT in args and api.PARAM_LNG in args and \
     (args[api.PARAM_LAT] != "" and args[api.PARAM_LNG] != ""):
    logging.debug("args[%s] = %s  args[%s] = %s" % 
      (api.PARAM_LAT, args[api.PARAM_LAT], api.PARAM_LNG, args[api.PARAM_LNG]))
    if api.PARAM_VOL_DIST not in args or args[api.PARAM_VOL_DIST] == "":
      args[api.PARAM_VOL_DIST] = 25
    args[api.PARAM_VOL_DIST] = int(str(args[api.PARAM_VOL_DIST]))
    if args[api.PARAM_VOL_DIST] < 1:
      args[api.PARAM_VOL_DIST] = 1
    max_dist = float(args[api.PARAM_VOL_DIST]) / 60

    # TODO: Re-add locationless listings as a query param.
    #lat, lng = float(args["lat"]), float(args["long"])
    #if (lat < 0.5 and lng < 0.5):
    #  solr_query += add_range_filter("latitude", '*', '0.5')
    #  solr_query += add_range_filter("longitude", '*', '0.5')
    #else:
    #  solr_query += add_range_filter("latitude",
    #                                  lat - max_dist, lat + max_dist)
    #  solr_query += add_range_filter("longitude",
    #                                  lng - max_dist, lng + max_dist)
    solr_query += build_function_query(args[api.PARAM_LAT],
                                       args[api.PARAM_LNG],
                                       max_dist,
                                       query_is_empty)
    
  if api.PARAM_CAMPAIGN_ID in args:
    # we need to exclude the opted out opprotunities
    # they can be tagged as opt_out_all_campaigns
    # or opt_out_campaign_XXX where XXX is the campaign ID.
    exclusion = '!categories:%s !categories:%s' % (
      'optout_all_campaigns',
      'optout_campaign_' + args[api.PARAM_CAMPAIGN_ID]
    )
    # TODO: campaign_ids are per-campaign, but opprotunities
    # might prefer to opt out of an entire sponsor.
    # should probablly add a 'sponsor_id' to the spreadsheet,
    # and have optout_sponsor_XXX as well.
    solr_query += exclusion

  solr_query = urllib.quote_plus(solr_query)

  # Specify which fields to return. Returning less fields decreases latency as
  # the search is performed on a different machine than the front-end.
  solr_query += '&fl='
  if api.PARAM_OUTPUT not in args:
    solr_query += api.DEFAULT_OUTPUT_FIELDS
  else:
    if args[api.PARAM_OUTPUT] in api.FIELDS_BY_OUTPUT_TYPE:
      solr_query += api.FIELDS_BY_OUTPUT_TYPE[args[api.PARAM_OUTPUT]]
    else:
      solr_query += '*'
  
  # TODO: injection attack on backend
  if api.PARAM_BACKEND_URL not in args:
    try:
      args[api.PARAM_BACKEND_URL] = private_keys.DEFAULT_BACKEND_URL_SOLR
    except:
      raise NameError("error reading private_keys.DEFAULT_BACKEND_URL_SOLR-- "+
                     "please install correct private_keys.py file")
  logging.info("backend="+args[api.PARAM_BACKEND_URL])

  if api.PARAM_START not in args:
    args[api.PARAM_START] = 1

  return solr_query

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
def search(args):
  """run a SOLR search."""
  def have_valid_query(args):
    """ make sure we were given a value for at least one of these arguments """
    valid_query = False
    api_list = [api.PARAM_Q,
                api.PARAM_TIMEPERIOD,
                api.PARAM_VOL_LOC,
                api.PARAM_VOL_STARTDATE,
                api.PARAM_VOL_ENDDATE,
                api.PARAM_VOL_DURATION,
                api.PARAM_VOL_PROVIDER,
                api.PARAM_VOL_STARTDAYOFWEEK]

    for param in api_list:
      if param in args and args[param]:
        if param == api.PARAM_VOL_LOC:
          # vol_loc must render a lat, long pair
          if (not args["lat"] or parseLatLng(args["lat"]) == 0 or 
              not args["long"] or parseLatLng(args["long"]) == 0):
            continue
        valid_query = True
        break
      
    return valid_query

  solr_query = form_solr_query(args)
  query_url = args[api.PARAM_BACKEND_URL]
  if query_url.find("?") < 0:
    # yeah yeah, should really parse the URL
    query_url += "?"

  # Return results in JSON format
  # TODO: return in TSV format for fastest possible parsing, i.e. split("\t") 
  query_url += "&wt=json"

  num_to_fetch = int(args[api.PARAM_NUM]) + 1
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

  logging.debug("calling SOLR: "+query_url)
  results = query(query_url, args, False)
  logging.debug("SOLR call done: "+str(len(results.results))+
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


def query(query_url, args, cache):
  """run the actual SOLR query (no filtering or sorting)."""
  #logging.info("Query URL: " + query_url + '&debugQuery=on')
  result_set = searchresult.SearchResultSet(urllib.unquote(query_url),
                                            query_url,
                                            [])

  result_set.query_url = query_url
  result_set.args = args
  result_set.fetch_time = 0
  result_set.parse_time = 0
  
  fetch_start = time.time()
  fetch_result = urlfetch.fetch(query_url,
                   deadline = api.CONST_MAX_FETCH_DEADLINE)
  fetch_end = time.time()
  result_set.fetch_time = fetch_end - fetch_start
  if fetch_result.status_code != 200:
    return result_set
  result_content = fetch_result.content

  parse_start = time.time()
  # undo comma encoding -- see datahub/footprint_lib.py
  result_content = re.sub(r';;', ',', result_content)
  result = simplejson.loads(result_content)
  doc_list = result["response"]["docs"]

  for i, entry in enumerate(doc_list):
    if not "detailurl" in entry:
      # URL is required
      latstr = entry["latitude"]
      longstr = entry["longitude"]
      if latstr and longstr and latstr != "" and longstr != "":
        entry["detailurl"] = "http://maps.google.com/maps?q=" + str(latstr) + "," + str(longstr)
      else:
        logging.warning("skipping SOLR record %d: detailurl is missing..." % i)
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
    categories = entry.get('categories', '').split(',')
    org_name = entry.get('org_name', '')
    if re.search(r'[^a-z]acorn[^a-z]', " "+org_name+" ", re.IGNORECASE):
      logging.warning("skipping: ACORN in org_name..")
      continue
    res = searchresult.SearchResult(url, title, snippet, location, item_id,
                                    base_url, categories, org_name)


    # TODO: escape?
    res.provider = entry["feed_providername"]
    if (res.provider == "myproj_servegov" and
        re.search(r'[^a-z]acorn[^a-z]', " "+result_content+" ", re.IGNORECASE)):
      # per-provider rule because case-insensitivity
      logging.warning("skipping: ACORN anywhere for myproj_servegov.")
      continue
    res.orig_idx = i+1
    res.latlong = ""
    latstr = entry["latitude"]
    longstr = entry["longitude"]
    if latstr and longstr and latstr != "" and longstr != "":
      if api.PARAM_VOL_DIST in args and args[api.PARAM_VOL_DIST] != "":
        # beyond distance from requested?
        try:
          max_vol_dist = float(args[api.PARAM_VOL_DIST])
          vol_lat = float(args["lat"])
          vol_lng = float(args["long"])
          result_lat = float(latstr)
          result_lng = float(longstr)
          miles_to_opp = (MILES_PER_DEG * pow(pow(vol_lat - result_lat, 2) 
                          + pow(vol_lng - result_lng, 2), 0.5))
          if miles_to_opp > max_vol_dist:
            logging.warning("skipping SOLR record %d: too far (%d > %d)" % 
              (i, miles_to_opp, max_vol_dist))
            continue
        except:
          logging.warning("could not calc %s max distance [%s,%s] to [%s,%s]" %
            (args[api.PARAM_VOL_DIST], args["lat"], args["long"], 
              latstr, longstr))

      res.latlong = str(latstr) + "," + str(longstr)

    # TODO: remove-- working around a DB bug where all latlongs are the same
    if "geocode_responses" in args:
      res.latlong = geocode.geocode(location,
            args["geocode_responses"]!="nocache" )

    # res.event_date_range follows one of these two formats:
    #     <start_date>T<start_time> <end_date>T<end_time>
    #     <date>T<time>
    res.event_date_range = entry["event_date_range"]
    res.startdate = datetime.datetime.strptime("2000-01-01", "%Y-%m-%d")
    res.enddate = datetime.datetime.strptime("2038-01-01", "%Y-%m-%d")
    if res.event_date_range:
      match = DATE_FORMAT_PATTERN.findall(res.event_date_range)
      if not match:
        logging.warning('skipping Base record %d: bad date range: %s for %s' %
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
    logging.warning('Could not find entry in datastore for ids: %s' %
                    datastore_missing_ids)

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
      logging.warning('no base_url in datastore for id: %s' % item_id)
      continue
    logging.info("Datastore Entry: " + volunteer_opportunity_entity.base_url) ##
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
      logging.error('First result is not expected result. '
                    'Expected: %s Found: %s. len(results): %s' %
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


