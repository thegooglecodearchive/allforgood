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
low-level routines for querying Google Base and processing the results.
Please don't call this directly-- instead call search.py
"""

import datetime
import time
import re
import urllib
import logging
import traceback

from google.appengine.api import memcache
from google.appengine.api import urlfetch
from xml.dom import minidom

import api
import geocode
import models
import modelutils
import posting
import searchresult
import utils

RESULT_CACHE_TIME = 900 # seconds
RESULT_CACHE_KEY = 'searchresult:'

# google base has a bug where negative numbers aren't indexed correctly,
# so we load the data with only positive numbers for lat/long.
# this should be a big number and of course must be sync'd with the
# value in datahub/*
GBASE_LOC_FIXUP = 1000

# Date format pattern used in date ranges.
DATE_FORMAT_PATTERN = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')

# max number of results to ask from Base (for latency-- and correctness?)
BASE_MAX_RESULTS = 1000

# what base customer/author ID did we load the data under?
BASE_CUSTOMER_ID = 5663714

def base_argname(name):
  """base-sepcific urlparams all start with "base_" to avoid conflicts with
  non-base-specific args, and also to signal to appwriters that they're base
  specific and to cautious about their usage."""
  return "base_" + name

def base_orderby_arg(args):
  """convert from footprint ranking/sorting order to Base order."""
  # TODO: implement other scenarios for orderby
  if args[api.PARAM_SORT] == "m":
    # newest
    return "modification_time"
  # "relevancy" is the Base default
  return "relevancy"

def base_restrict_str(key, val=None):
  """convert from key=val to Base restrict syntax."""
  res = '+[' + urllib.quote_plus(re.sub(r'_', r' ', key))
  if val != None:
    res += ':' + urllib.quote_plus(str(val))
  return res + ']'

def form_base_query(args):
  """ensure args[] has all correct and well-formed members and
  return a base query string."""
  logging.debug("form_base_query: "+str(args))
  base_query = ""
  if api.PARAM_Q in args and args[api.PARAM_Q] != "":
    base_query += urllib.quote_plus(args[api.PARAM_Q])

  if api.PARAM_VOL_STARTDATE in args or api.PARAM_VOL_ENDDATE in args:
    startdate = None
    if api.PARAM_VOL_STARTDATE in args and args[api.PARAM_VOL_STARTDATE] != "":
      try:
        startdate = datetime.datetime.strptime(
                       args[api.PARAM_VOL_STARTDATE].strip(), "%Y-%m-%d")
      except:
        logging.error("malformed start date: %s" % 
           args[api.PARAM_VOL_STARTDATE])
    if not startdate:
      # note: default vol_startdate is "tomorrow"
      # in base, event_date_range YYYY-MM-DDThh:mm:ss/YYYY-MM-DDThh:mm:ss
      # appending "Z" to the datetime string would mean UTC
      startdate = datetime.date.today() + datetime.timedelta(days=1)
      args[api.PARAM_VOL_STARTDATE] = startdate.strftime("%Y-%m-%d")

    enddate = None
    if api.PARAM_VOL_ENDDATE in args and args[api.PARAM_VOL_ENDDATE] != "":
      try:
        enddate = datetime.datetime.strptime(
                       args[api.PARAM_VOL_ENDDATE].strip(), "%Y-%m-%d")
      except:
        logging.error("malformed end date: %s" % args[api.PARAM_VOL_ENDDATE])
    if not enddate:
      enddate = datetime.date(startdate.year, startdate.month, startdate.day)
      enddate = enddate + datetime.timedelta(days=1000)
      args[api.PARAM_VOL_ENDDATE] = enddate.strftime("%Y-%m-%d")
    daterangestr = '%s..%s' % (args[api.PARAM_VOL_STARTDATE], 
                       args[api.PARAM_VOL_ENDDATE])
    base_query += base_restrict_str("event_date_range", daterangestr)

  if api.PARAM_VOL_PROVIDER in args and args[api.PARAM_VOL_PROVIDER] != "":
    if re.match(r'[a-zA-Z0-9:/_. -]+', args[api.PARAM_VOL_PROVIDER]):
      base_query += base_restrict_str("feed_providername", 
                       args[api.PARAM_VOL_PROVIDER])
    else:
      # illegal providername
      # TODO: throw 500
      logging.error("illegal providername: " + args[api.PARAM_VOL_PROVIDER])

  # TODO: injection attack on sort
  if api.PARAM_SORT not in args:
    args[api.PARAM_SORT] = "r"

  # Base location datatype is buggy-- use inequality search on lat/long
  #base_query += base_restrict_str("location", '@"%s" + %dmi' % \
  #                                  (args[api.PARAM_VOL_LOC],
  #                                   args[api.PARAM_VOL_DIST]))
  if (args["lat"] != "" and args["long"] != ""):
    logging.debug("args[lat]="+args["lat"]+"  args[long]="+args["long"])
    if api.PARAM_VOL_DIST not in args or args[api.PARAM_VOL_DIST] == "":
      args[api.PARAM_VOL_DIST] = 25
    args[api.PARAM_VOL_DIST] = int(str(args[api.PARAM_VOL_DIST]))
    if args[api.PARAM_VOL_DIST] < 1:
      args[api.PARAM_VOL_DIST] = 1
    lat, lng = float(args["lat"]), float(args["long"])
    if (lat < 0.5 and lng < 0.5):
      base_query += "[latitude%3C%3D0.5][longitude%3C%3D0.5]"
    else:
      dist = float(args[api.PARAM_VOL_DIST])
      base_query += "[latitude%%3E%%3D%.2f]" % (lat+GBASE_LOC_FIXUP - dist/69.1)
      base_query += "[latitude%%3C%%3D%.2f]" % (lat+GBASE_LOC_FIXUP + dist/69.1)
      base_query += "[longitude%%3E%%3D%.2f]" % (lng+GBASE_LOC_FIXUP - dist/50)
      base_query += "[longitude%%3C%%3D%.2f]" % (lng+GBASE_LOC_FIXUP + dist/50)

  # Base URL for snippets search on Base.
  #   Docs: http://code.google.com/apis/base/docs/2.0/attrs-queries.html
  # TODO: injection attack on backend
  if api.PARAM_BACKEND_URL not in args:
    args[api.PARAM_BACKEND_URL] = "http://www.google.com/base/feeds/snippets"

  cust_arg = base_argname("customer")
  if cust_arg not in args:
    args[cust_arg] = BASE_CUSTOMER_ID
  base_query += base_restrict_str("customer_id", int(args[cust_arg]))

  #base_query += base_restrict_str("detailurl")

  if api.PARAM_START not in args:
    args[api.PARAM_START] = 1

  # TODO: remove me-- hack to forcibly remove DNC listings for now
  # (Base hasn't caught up to the takedown, not sure why...)
  #base_query += '+-barackobama'

  return base_query

# note: many of the XSS and injection-attack defenses are unnecessary
# given that the callers are also protecting us, but I figure better
# safe than sorry, and defense-in-depth.
def search(args):
  """run a Google Base search."""
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

  base_query = form_base_query(args)
  query_url = args[api.PARAM_BACKEND_URL]
  num_to_fetch = int(args[api.PARAM_START])
  num_to_fetch += int(args[api.PARAM_NUM] * args[api.PARAM_OVERFETCH_RATIO])
  if num_to_fetch > BASE_MAX_RESULTS:
    num_to_fetch = BASE_MAX_RESULTS
  query_url += "?max-results=" + str(num_to_fetch)

  # We don't set "&start-index=" because that will interfere with
  # deduping + pagination.  Since we merge the results here in the
  # app, we must perform de-duping starting at index zero every time
  # in order to get reliable pagination.

  query_url += "&orderby=" + base_orderby_arg(args)
  query_url += "&content=" + "all"
  query_url += "&bq=" + base_query

  if not have_valid_query(args):
    # no query + no location = no results
    result_set = searchresult.SearchResultSet(urllib.unquote(query_url),
                                            query_url,
                                            [])
    logging.debug("Base not called: no query given")
    result_set.query_url = query_url
    result_set.args = args
    result_set.num_results = 0
    result_set.estimated_results = 0
    result_set.fetch_time = 0
    result_set.parse_time = 0
    return result_set

  logging.debug("calling Base: "+query_url)
  results = query(query_url, args, False)
  logging.debug("Base call done: "+str(len(results.results))+
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
  """run the actual Base query (no filtering or sorting)."""
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
    logging.error("Base fetch returned status code "+
                  str(fetch_result.status_code)+
                  "  url="+query_url)
    return result_set
  result_content = fetch_result.content

  parse_start = time.time()
  # undo comma encoding -- see datahub/footprint_lib.py
  result_content = re.sub(r';;', ',', result_content)
  dom = minidom.parseString(result_content)
  elems = dom.getElementsByTagName('entry')
  for i, entry in enumerate(elems):
    # Note: using entry.getElementsByTagName('link')[0] isn't very stable;
    # consider iterating through them for the one where rel='alternate' or
    # whatever the right thing is.
    url = utils.xml_elem_text(entry, 'g:detailurl', '')
    if not url:
      logging.warning("skipping Base record %d: detailurl is missing..." % i)
      continue

    # ID is the 'stable id' of the item generated by base.
    # Note that this is not the base url expressed as the Atom id element.
    item_id = utils.xml_elem_text(entry, 'g:id', '')
    # Base URL is the url of the item in base, expressed with the Atom id tag.
    base_url = utils.xml_elem_text(entry, 'id', '')
    snippet = utils.xml_elem_text(entry, 'g:abstract', '')
    title = utils.xml_elem_text(entry, 'title', '')
    location = utils.xml_elem_text(entry, 'g:location_string', '')
    res = searchresult.SearchResult(url, title, snippet, location, item_id,
                                    base_url)

    # TODO: escape?
    res.provider = utils.xml_elem_text(entry, 'g:feed_providername', '')
    res.orig_idx = i+1
    res.latlong = ""
    latstr = utils.xml_elem_text(entry, 'g:latitude', '')
    longstr = utils.xml_elem_text(entry, 'g:longitude', '')
    if latstr and longstr and latstr != "" and longstr != "":
      latval = float(latstr)
      longval = float(longstr)
      # divide by two because these can be negative numbers
      if latval > GBASE_LOC_FIXUP/2:
        latval -= GBASE_LOC_FIXUP
      if longval > GBASE_LOC_FIXUP/2:
        longval -= GBASE_LOC_FIXUP
      res.latlong = str(latval) + "," + str(longval)

    # TODO: remove-- working around a DB bug where all latlongs are the same
    if "geocode_responses" in args:
      res.latlong = geocode.geocode(location,
            args["geocode_responses"]!="nocache" )

    # res.event_date_range follows one of these two formats:
    #     <start_date>T<start_time> <end_date>T<end_time>
    #     <date>T<time>
    res.event_date_range = utils.xml_elem_text(entry, 'g:event_date_range' '')
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
        setattr(res, name, utils.xml_elem_text(entry, "g:" + name, ''))

    result_set.results.append(res)
    if cache and res.item_id:
      key = RESULT_CACHE_KEY + res.item_id
      memcache.set(key, res, time=RESULT_CACHE_TIME)

  result_set.num_results = len(result_set.results)
  result_set.estimated_results = int(
    utils.xml_elem_text(dom, "openSearch:totalResults", "0"))
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
    temp_results = query(volunteer_opportunity_entity.base_url, args, True)
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
