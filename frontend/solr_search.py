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
from google.appengine.api import memcache
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

def solr_format_range(field, min_val, max_val):
  """ Convert colons in the field name and build a range specifier
  in SOLR query syntax"""
  # TODO: Deal with escapification
  result = ' AND '
  result += field
  result += ':[' + str(min_val) +' TO ' + str(max_val) + ']'
  return result

def rewrite_query(query):
  """ Rewrites the query string from an easy to type and understand format
  into a Solr-readable format"""
  return query.replace('category:', 'c\:categories\:string:')
  

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

  if api.PARAM_VOL_STARTDATE in args or api.PARAM_VOL_ENDDATE in args:
    startdate = None
    if api.PARAM_VOL_STARTDATE in args and args[api.PARAM_VOL_STARTDATE] != "":
      try:
        startdate = datetime.datetime.strptime(
                       args[api.PARAM_VOL_STARTDATE].strip(), "%Y%m%d")
      except:
        logging.error("malformed start date: %s" % 
           args[api.PARAM_VOL_STARTDATE])
    if not startdate:
      # note: default vol_startdate is "tomorrow"
      # in base, event_date_range YYYY-MM-DDThh:mm:ss/YYYY-MM-DDThh:mm:ss
      # appending "Z" to the datetime string would mean UTC
      startdate = datetime.date.today() + datetime.timedelta(days=1)
      args[api.PARAM_VOL_STARTDATE] = startdate.strftime("%Y%m%d")

    enddate = None
    if api.PARAM_VOL_ENDDATE in args and args[api.PARAM_VOL_ENDDATE] != "":
      try:
        enddate = datetime.datetime.strptime(
                       args[api.PARAM_VOL_ENDDATE].strip(), "%Y%m%d")
      except:
        logging.error("malformed end date: %s" % args[api.PARAM_VOL_ENDDATE])
    if not enddate:
      enddate = datetime.date(startdate.year, startdate.month, startdate.day)
      enddate = enddate + datetime.timedelta(days=1000)
      args[api.PARAM_VOL_ENDDATE] = enddate.strftime("%Y%m%d")

    solr_query += solr_format_range("c\:eventrangestart\:datetime", '*',
                                     args[api.PARAM_VOL_ENDDATE])
    solr_query += solr_format_range("c\:eventrangeend\:datetime",
                                    args[api.PARAM_VOL_STARTDATE], '*')

  if api.PARAM_VOL_PROVIDER in args and args[api.PARAM_VOL_PROVIDER] != "":
    if re.match(r'[a-zA-Z0-9:/_. -]+', args[api.PARAM_VOL_PROVIDER]):
      solr_query += " AND c\:feed_providerName\:string:" + \
                      args[api.PARAM_VOL_PROVIDER]
    else:
      # illegal providername
      # TODO: throw 500
      logging.error("illegal providername: " + args[api.PARAM_VOL_PROVIDER])
  solr_query = urllib.quote_plus(solr_query)
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
    solr_query += '&qt=geo'
    solr_query += '&lat=' + args["lat"]
    solr_query += '&long=' + args["long"]
    solr_query += '&radius=' + str(args[api.PARAM_VOL_DIST])
    #Todo: implement sorting by distance.
    #solr_query += "&sort=geo_distance+asc"

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
  #logging.info("Query URL: " + query_url)
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
    # Note: using entry.getElementsByTagName('link')[0] isn't very stable;
    # consider iterating through them for the one where rel='alternate' or
    # whatever the right thing is.
    url = entry["c:detailURL:URL"]
    if not url:
      # URL is required
      logging.warning("skipping Base record %d: detailurl is missing..." % i)
      continue
    # ID is the 'stable id' of the item generated by base.
    # Note that this is not the base url expressed as the Atom id element.
    item_id = entry["id"]
    # Base URL is the url of the item in base, expressed with the Atom id tag.
    # TODO: This doesn't seem to be used. Consider removing it.
    base_url = ""
    snippet = entry["c:abstract:string"]
    title = entry["title"]
    location = entry["c:location_string:string"]
    res = searchresult.SearchResult(url, title, snippet, location, item_id,
                                    base_url)

    # TODO: escape?
    res.provider = entry["c:feed_providerName:string"]
    res.orig_idx = i+1
    res.latlong = ""
    latstr = entry["c:latitude:float"]
    longstr = entry["c:longitude:float"]
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
        # TODO: Should this be entry["c:" + name]?
        setattr(res, name, ["c:" + name])

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
