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
from operator import itemgetter

import api
import geocode
import ical_filter
import models
import modelutils
import posting
import private_keys
import boosts
import categories
import searchresult

RESULT_CACHE_TIME = 900 # seconds
RESULT_CACHE_KEY = 'searchresult:'
KEYWORD_GLOBAL = ""
GEO_GLOBAL = ""
PROVIDER_GLOBAL = ""
FULL_QUERY_GLOBAL = ""
DATE_QUERY_GLOBAL = ""
BACKEND_GLOBAL = ""

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
    boost += '+eventrangestart:[NOW+TO+*]^5'    
    # modest penalty for events started long ago
    boost += '+eventrangestart:[NOW-6MONTHS+TO+*]^7'    
    # modest penalty for events ending in the far future
    boost += '+eventrangeend:[*+TO+NOW%2B6MONTHS]^7'     
    # big boost for events ending in the near future
    boost += '+eventrangeend:[NOW+TO+NOW%2B1MONTHS]^10'
    # slight penalty for meetup events
    boost += '+-feed_providername:meetup^2'
    # boost short events
    boost += '+eventduration:[1+TO+10]^10'
  
  #if api.PARAM_Q in args and args[api.PARAM_Q] != "" and api.PARAM_TYPE not in args:    
    # big boost opps with search terms in title
    #boost += '&qf=title^20'
    # modest boost opps with search terms in description
    #boost += '+abstract^7'
  
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
    args[api.PARAM_SORT] = "score"

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
  
  geo_params = '{!spatial lat=' + str(lat) + ' long=' + str(lng) + ' radius=' + str(max_dist) + ' boost=recip(dist(geo_distance),1,1000,1000)^1}'
  global GEO_GLOBAL
  GEO_GLOBAL = urllib.quote_plus(geo_params)
  if api.PARAM_TYPE in args and args[api.PARAM_TYPE] != "all":
      geo_params = ""       

  # Running our keyword through our categories dictionary to see if we need to adjust our keyword param   
  if api.PARAM_CATEGORY in args:
    for key, val in categories.CATEGORIES.iteritems():
      if str(args[api.PARAM_CATEGORY]) == val:
        args[api.PARAM_CATEGORY] = str(key)   

  # keyword
  query_is_empty = False
  if (api.PARAM_Q in args and args[api.PARAM_Q] != ""):
    qwords = args[api.PARAM_Q].split(" ")
    for qi, qw in enumerate(qwords):
      # it is common practice to use a substr of a url eg, volunteermatch 
      # here we transform that to http://*volunteermatch* 
      if qw.find("detailurl:") >= 0 and qw.find("*") < 0:
        ar = qw.split(":")
        if len(ar) > 1:
          ar[1] = "http*" + ar[1] + "*"
          qw = ":".join(ar)
          qwords[qi] = qw
          args[api.PARAM_Q] = ' '.join(qwords)

    query_boosts = boosts.query_time_boosts(args)
    
    # Remove categories from query parameter    
    args[api.PARAM_Q] = args[api.PARAM_Q].replace('category:', '')
    
    if api.PARAM_CATEGORY in args:        
        args[api.PARAM_Q] += (" AND " + args[api.PARAM_CATEGORY])
    
    if query_boosts:
      solr_query = query_boosts    
    else:
      solr_query += rewrite_query('*:* AND ' +  args[api.PARAM_Q], api_key)
  elif api.PARAM_CATEGORY in args:
      solr_query += rewrite_query('*:* AND ' +  args[api.PARAM_CATEGORY], api_key)
  else:
    # Query is empty, search for anything at all.
    solr_query += rewrite_query('*:*', api_key)
    query_is_empty = True

  # geo params go in first
  global KEYWORD_GLOBAL
  KEYWORD_GLOBAL = urllib.quote_plus(solr_query)
  solr_query = geo_params + solr_query
  solr_query = urllib.quote_plus(solr_query)
  
  # Type
  if api.PARAM_TYPE in args and args[api.PARAM_TYPE] != "all":
    if args[api.PARAM_TYPE] == "self_directed":
      solr_query += "+AND+self_directed:true"    
    elif args[api.PARAM_TYPE] == "virtual":
      solr_query += "+AND+virtual:true+AND+micro:false+AND+self_directed:false"
    elif args[api.PARAM_TYPE] == "micro":
      solr_query += "+AND+micro:true"
  else:
      solr_query += "&fq=self_directed:false+AND+virtual:false+AND+micro:false"
  global FULL_QUERY_GLOBAL
  FULL_QUERY_GLOBAL =  solr_query
    
  # Source
  global PROVIDER_GLOBAL
  if api.PARAM_SOURCE in args and args[api.PARAM_SOURCE] != "all":    
    PROVIDER_GLOBAL = "+AND+provider_proper_name:" + urllib.quote_plus("(" + args[api.PARAM_SOURCE] + ")")
    solr_query += PROVIDER_GLOBAL
  else:
    PROVIDER_GLOBAL = ""  
      
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
    today = datetime.date.today()
    weekday = datetime.date.today().weekday()
    try:
      if weekday in [0,2,4,6]:
        args[api.PARAM_BACKEND_URL] = private_keys.NODE1_DEFAULT_BACKEND_URL
      else:
        args[api.PARAM_BACKEND_URL] = private_keys.NODE2_DEFAULT_BACKEND_URL
    except:
      raise NameError("error reading private_keys.DEFAULT_BACKEND_URL_SOLR-- " +
                      "please install correct private_keys.py file")
    global BACKEND_GLOBAL
    BACKEND_GLOBAL = args[api.PARAM_BACKEND_URL]
  
  # field list
  solr_query += '&fl='
  if api.PARAM_OUTPUT not in args:
    solr_query += api.DEFAULT_OUTPUT_FIELDS
  else:
    if args[api.PARAM_OUTPUT] in api.FIELDS_BY_OUTPUT_TYPE:
      solr_query += api.FIELDS_BY_OUTPUT_TYPE[args[api.PARAM_OUTPUT]]
    else:
      solr_query += '*' 

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
  if api.PARAM_SORT in args:
    sortVal = "desc"
    if args[api.PARAM_SORT] == "eventrangeend":
       sortVal = "asc"
    query_url += "&sort=" + args[api.PARAM_SORT] + "%20" + sortVal
    
  # date range
  date_string = ""
  start_datetime_str = None
  if api.PARAM_VOL_STARTDATE in args and args[api.PARAM_VOL_STARTDATE] != "" and args[api.PARAM_VOL_STARTDATE] != "everything":    
    start_date = datetime.datetime.today()
    try:
      start_date = datetime.datetime.strptime(
                     args[api.PARAM_VOL_STARTDATE].strip(), "%m/%d/%Y")      
    except:
      logging.info('solr_search.form_solr_query malformed start date: %s' %
                    args[api.PARAM_VOL_STARTDATE])
    end_date = None
    if api.PARAM_VOL_ENDDATE in args and args[api.PARAM_VOL_ENDDATE] != "":
      try:
        end_date = datetime.datetime.strptime(
                       args[api.PARAM_VOL_ENDDATE].strip(), "%m/%d/%Y")
      except:
        logging.debug('solr_search.form_solr_query malformed end date: %s' %
                       args[api.PARAM_VOL_ENDDATE])
    if not end_date:
      end_date = start_date
    start_datetime_str = start_date.strftime("%Y-%m-%dT00:00:00.000Z")
    end_datetime_str = end_date.strftime("%Y-%m-%dT23:59:59.999Z")
  
  global DATE_QUERY_GLOBAL
  if start_datetime_str:
    DATE_QUERY_GLOBAL = "&fq=((eventrangeend:[" + start_datetime_str + "+TO+*]+AND+eventrangestart:[*+TO+" + end_datetime_str + "])+OR+(eventrangeend:+" +'"1971-01-01T00:00:000Z"' "+AND+eventrangestart:"+'"1971-01-01T00:00:000Z"'+"))"
    query_url += DATE_QUERY_GLOBAL
  else:
    DATE_QUERY_GLOBAL = "&fq=(eventrangeend:[NOW-3DAYS%20TO%20*]+OR+expires:[NOW-3DAYS%20TO%20*])"
    query_url += DATE_QUERY_GLOBAL

  #num_to_fetch = int(args[api.PARAM_NUM]) + 1
  num_to_fetch = 100
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
  all_facets = get_geo_counts()
  if "facet_counts" in all_facets:    
    facet_counts = dict()    
    facet_counts["all"] = int(all_facets["facet_counts"]["facet_queries"]["self_directed:false AND virtual:false AND micro:false"])
    facet_counts.update(get_type_counts())    
    
    count = 0;
    if api.PARAM_TYPE in args:
        if args[api.PARAM_TYPE] == "virtual":
            count = facet_counts["virtual"]
        elif args[api.PARAM_TYPE] == "self_directed":
            count = facet_counts["self_directed"]
        elif args[api.PARAM_TYPE] == "micro":
            count = facet_counts["micro"]
        else:
            count = facet_counts["all"]

    facet_counts["count"] = count
    
    result_set.facet_counts = facet_counts
    facets = get_facet_counts()
    result_set.categories = facets['category_fields']
    result_set.providers = facets['provider_fields']
    
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
    snippet = entry.get('description', '')
    title = entry.get('title', '')
    location = entry.get('location_string', '')

    cat = entry.get('categories', '')
    if type(cat).__name__ != 'list':
      try:
        cat = cat.split(',')
      except:
        cat = []
    
    org_name = entry.get('org_name', '')
    if re.search(r'[^a-z]acorn[^a-z]', " "+org_name+" ", re.IGNORECASE):
      logging.debug('solr_search.query skipping: ACORN in org_name')
      continue
    latstr = entry["latitude"]
    longstr = entry["longitude"]
    virtual = entry.get('virtual')
    self_directed = entry.get("self_directed")
    micro = entry.get("micro")
    volunteers_needed = entry.get("volunteersneeded")
    res = searchresult.SearchResult(url, title, snippet, location, item_id,
                                    base_url, volunteers_needed, virtual,
                                    self_directed, micro, cat, org_name)

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

    """openended = "openended" in entry and entry["openended"]
    if openended and "ical_recurrence" in entry:
      ical_recurrence = entry["ical_recurrence"]
      query_startdate = args[api.PARAM_VOL_STARTDATE] if api.PARAM_VOL_STARTDATE in args else None
      query_enddate = args[api.PARAM_VOL_ENDDATE] if api.PARAM_VOL_ENDDATE in args else None
      if not ical_filter.match(ical_recurrence, query_startdate, query_enddate):
        logging.warning("skipping SOLR record %d: failed the iCal filter" % i)
        continue"""

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

def get_facet_counts():
    category_fields = dict()
    provider_fields = []
    query = []
    for key, val in categories.CATEGORIES.iteritems():
      query.append("facet.query=" + urllib.quote_plus(key))  

    try:
        query_url = BACKEND_GLOBAL + '?wt=json' + DATE_QUERY_GLOBAL + '&q=' + FULL_QUERY_GLOBAL + PROVIDER_GLOBAL + '&facet.mincount=1&facet.field=provider_proper_name_str&facet=on&rows=0&' + "&".join(query)
        logging.info("facets: " + query_url)
    except:
        raise NameError("error reading private_keys.DEFAULT_BACKEND_URL_SOLR-- please install correct private_keys.py file")
    try:
        fetch_result = urlfetch.fetch(query_url, deadline = api.CONST_MAX_FETCH_DEADLINE)
    except:
        logging.info('error receiving solr facet counts')

    result_content = fetch_result.content
    result_content = re.sub(r';;', ',', result_content)
    json = simplejson.loads(result_content)["facet_counts"]
    queries = json["facet_queries"]
    providers = json["facet_fields"]["provider_proper_name_str"]
    
    for k, v in queries.iteritems():
        if v > 0:
            category_fields[categories.CATEGORIES[k]] = v
    
    for k, v in enumerate(providers):
        if int(k) % 2 == 1:
            continue;
        else:
            provider_fields.append({str(v) : str(providers[k + 1])})
    
    return {'category_fields': sorted(category_fields.iteritems(), key=itemgetter(1), reverse=True), 'provider_fields': provider_fields}    

def get_geo_counts():
  try:
    query_url = BACKEND_GLOBAL + '?wt=json' + DATE_QUERY_GLOBAL + '&q=' + GEO_GLOBAL + KEYWORD_GLOBAL + PROVIDER_GLOBAL + '&facet=on&facet.mincount=1&facet.query=self_directed:false+AND+virtual:false+AND+micro:false&rows=0'
    logging.info("all: " + query_url)
  except:
    raise NameError("error reading private_keys.DEFAULT_BACKEND_URL_SOLR-- please install correct private_keys.py file")
  try:
    fetch_result = urlfetch.fetch(query_url, deadline = api.CONST_MAX_FETCH_DEADLINE)
  except:
      logging.info('error receiving solr facet counts')
  
  result_content = fetch_result.content  
  # undo comma encoding -- see datahub/footprint_lib.py
  result_content = re.sub(r';;', ',', result_content)
  return simplejson.loads(result_content)


def get_type_counts():
  try:
    query_url = BACKEND_GLOBAL + '?wt=json' + DATE_QUERY_GLOBAL + '&q=' + KEYWORD_GLOBAL + PROVIDER_GLOBAL + '&facet=on&facet.limit=2&facet.field=virtual&facet.field=self_directed&facet.field=micro&rows=0'
    logging.info("type: " + query_url)
  except:
    raise NameError("error reading private_keys.DEFAULT_BACKEND_URL_SOLR-- please install correct private_keys.py file")
  try:
    fetch_result = urlfetch.fetch(query_url, deadline = api.CONST_MAX_FETCH_DEADLINE)
  except:
      logging.info('error receiving solr facet counts')
  
  result_content = fetch_result.content  
  # undo comma encoding -- see datahub/footprint_lib.py
  result_content = re.sub(r';;', ',', result_content)
  result = simplejson.loads(result_content)
  #facet_counts
  if "facet_counts" in result:
    facet_fields = result["facet_counts"]["facet_fields"]
    facet_counts = dict()
    for k, v in facet_fields.iteritems():
        if "true" in v:
          index = v.index("true")
        else:
          index = -1        
        if index >= 0:
          facet_counts[k] = v[index + 1]
        else:
          facet_counts[k] = 0
    facet_counts["virtual"] -= facet_counts["micro"] #hack to remove micro counts because they were incorrectly tagged as virtual
    facet_counts["virtual"] -= facet_counts["self_directed"] #hack to remove self_directed counts because they were incorrectly tagged as virtual
  return facet_counts
