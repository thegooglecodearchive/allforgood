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
import urllib

from django.utils import simplejson
from versioned_memcache import memcache
from google.appengine.api import urlfetch

import api
import geocode
import posting
import private_keys
import searchresult

RESULT_CACHE_TIME = 900 # seconds
RESULT_CACHE_KEY = 'searchresult:'

# Date format pattern used in date ranges.
DATE_FORMAT_PATTERN = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')

# max number of results to ask from SOLR (for latency-- and correctness?)
MAX_RESULTS = 1000

def build_function_query(base_lat, base_long, max_dist):
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
  
  function_query = ' AND _val_:"'
  function_query += 'sum(' + geo_score_str + ',' + duration_score_str + ')'
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
  if api.PARAM_Q in args and args[api.PARAM_Q] != "":
    solr_query += rewrite_query(args[api.PARAM_Q])
  else:
    # Query is empty, search for anything at all.
    solr_query += "*:*"

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
      solr_query += " AND feed_providerName:" + \
                      args[api.PARAM_VOL_PROVIDER]
    else:
      # illegal providername
      # TODO: throw 500
      logging.error("illegal providername: " + args[api.PARAM_VOL_PROVIDER])
  # TODO: injection attack on sort
  if api.PARAM_SORT not in args:
    args[api.PARAM_SORT] = "r"

  # Generate geo search parameters
  if (args["lat"] != "" and args["long"] != ""):
    logging.debug("args[lat]="+args["lat"]+"  args[long]="+args["long"])
    if api.PARAM_VOL_DIST not in args or args[api.PARAM_VOL_DIST] == "":
      args[api.PARAM_VOL_DIST] = 25
    args[api.PARAM_VOL_DIST] = int(str(args[api.PARAM_VOL_DIST]))
    if args[api.PARAM_VOL_DIST] < 1:
      args[api.PARAM_VOL_DIST] = 1

    lat, lng = float(args["lat"]), float(args["long"])
    max_dist = float(args[api.PARAM_VOL_DIST]) / 60
    if (lat < 0.5 and lng < 0.5):
      solr_query += add_range_filter("latitude", '*', '0.5')
      solr_query += add_range_filter("longitude", '*', '0.5')
    else:
      solr_query += add_range_filter("latitude",
                                      lat - max_dist, lat + max_dist)
      solr_query += add_range_filter("longitude",
                                      lng - max_dist, lng + max_dist)
    solr_query += build_function_query(args["lat"], args["long"], max_dist)    
  solr_query = urllib.quote_plus(solr_query)

#    solr_query += '&qt=geo'
#    solr_query += '&lat=' + args["lat"]
#    solr_query += '&long=' + args["long"]
#    solr_query += '&radius=' + str(args[api.PARAM_VOL_DIST])

  # TODO: injection attack on backend
  if api.PARAM_BACKEND_URL not in args:
    args[api.PARAM_BACKEND_URL] = private_keys.DEFAULT_BACKEND_URL_SOLR

  if api.PARAM_START not in args:
    args[api.PARAM_START] = 1
  return solr_query

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
          if not args["lat"] or not args["long"]:
            continue
        valid_query = True
        break
      
    return valid_query

  solr_query = form_solr_query(args)
  query_url = args[api.PARAM_BACKEND_URL]
  # Return results in JSON format
  # TODO: return in TSV format for fastest possible parsing, i.e. split("\t") 
  query_url += "?wt=json"

  num_to_fetch = int(args[api.PARAM_START])
  num_to_fetch += int(args[api.PARAM_NUM] * args[api.PARAM_OVERFETCH_RATIO])
  if num_to_fetch > MAX_RESULTS:
    num_to_fetch = MAX_RESULTS
  query_url += "&rows=" + str(num_to_fetch)

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
    if not "detailURL" in entry:
      # URL is required
      logging.warning("skipping Base record %d: detailurl is missing..." % i)
      continue
    url = entry["detailURL"]
    # ID is the 'stable id' of the item generated by base.
    # Note that this is not the base url expressed as the Atom id element.
    item_id = entry["id"]
    # Base URL is the url of the item in base, expressed with the Atom id tag.
    # TODO: This doesn't seem to be used. Consider removing it.
    base_url = ""
    snippet = entry.get('abstract', '')
    title = entry.get('title', '')
    location = entry.get('location_string', '')
    res = searchresult.SearchResult(url, title, snippet, location, item_id,
                                    base_url)

    # TODO: escape?
    res.provider = entry["feed_providerName"]
    res.orig_idx = i+1
    res.latlong = ""
    latstr = entry["latitude"]
    longstr = entry["longitude"]
    if latstr and longstr and latstr != "" and longstr != "":
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
      if name not in except_names:
        # these attributes are likely to become part of the "g" namespace
        # http://base.google.com/support/bin/answer.py?answer=58085&hl=en
        setattr(res, name, name)

    result_set.results.append(res)
    if cache and res.item_id:
      key = RESULT_CACHE_KEY + res.item_id
      memcache.set(key, res, time=RESULT_CACHE_TIME)

  result_set.num_results = len(result_set.results)
  result_set.estimated_results = int(
    result["response"]["numFound"])
  parse_end = time.time()
  result_set.parse_time = parse_end - parse_start
  return result_set