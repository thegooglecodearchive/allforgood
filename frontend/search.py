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
high-level routines for querying backend datastores and processing the results.
"""

import calendar
import datetime
import hashlib
import logging
import copy

from versioned_memcache import memcache
from utils import safe_str, safe_int

import api
import base_search
import geocode
from fastpageviews import pagecount
import scoring
import solr_search
import re

from query_rewriter import get_rewriters

CACHE_TIME = 24*60*60  # seconds

# bf=arg1[val1]:arg2[val2]:arg3[val3]|arg1[val1]:arg2[val2]:arg3[val3]|...
# qhere args are like 'q' for the query string
BACKFILL_QUERY_SEP = '|'
BACKFILL_ARG_SEP = ':'

def run_query_rewriters(query):
  rewriters = get_rewriters()
  query = rewriters.rewrite_query(query)
  return query

# args is expected to be a list of args
# and any path info is supposed to be homogenized into this,
# e.g. /listing/56_foo should be resolved into [('id',56)]
# by convention, repeated args are ignored, LAST ONE wins.
def search(args):
  """run a search against the backend specified by the 'backend' arg.
  Returns a result set that's been (a) de-dup'd ("merged") and (b) truncated
  to the appropriate number of results ("clipped").  Impression tracking
  happens here as well."""

  # TODO(paul): Create a QueryParams object to handle validation.
  #     Validation should be lazy, so that (for example) here
  #     only 'num' and 'start' are validated, since we don't
  #     yet need the rest.  QueryParams can have a function to
  #     create a normalized string, for the memcache key.
  # pylint: disable-msg=C0321
  
  normalize_query_values(args)

  # TODO: query param (& add to spec) for defeating the cache (incl FastNet)
  # I (mblain) suggest using "zx", which is used at Google for most services.

  # TODO: Should construct our own normalized query string instead of
  # using the browser's querystring.

  args_array = [str(key)+'='+str(value) for (key, value) in args.items()]
  args_array.sort()
  normalized_query_string = str('&'.join(args_array))

  use_cache = True
  if api.PARAM_CACHE in args and args[api.PARAM_CACHE] == '0':
    use_cache = False
    logging.debug('Not using search cache')

  # note: key cannot exceed 250 bytes
  memcache_key = hashlib.md5('search:' + normalized_query_string).hexdigest()
  start = safe_int(args[api.PARAM_START], api.CONST_MIN_START)
  num = safe_int(args[api.PARAM_NUM], api.CONST_DFLT_NUM)

  result_set = None
  if use_cache:
    result_set = memcache.get(memcache_key)
    if result_set:
      logging.debug('in cache: "' + normalized_query_string + '"')
      if len(result_set.merged_results) < start + num:
        logging.debug('but too small-- rerunning query...')
        result_set = None
    else:
      logging.debug('not in cache: "' + normalized_query_string + '"')

  if not result_set:
    result_set = fetch_result_set(args)
    memcache.set(memcache_key, result_set, time=CACHE_TIME)

  result_set.clip_merged_results(start, num)
  # TODO: for better results, we should segment CTR computation by
  # homepage vs. search views, etc. -- but IMHO it's better to give
  # up and outsource stats to a web-hosted service.
  if 'key' in args and args['key'] == pagecount.TEST_API_KEY:
    logging.debug("search(): not tracking testapi key views")
    # needed to populate stats
    result_set.track_views(num_to_incr=0)
  else:
    result_set.track_views(num_to_incr=1)
  return result_set

def min_max(val, minval, maxval):
  return max(min(maxval, val), minval)

def normalize_query_values(args):
  """Pre-processes several values related to the search API that might be
  present in the query string."""

  # api.PARAM_OUTPUT is only used by callers (the view)
  #   (though I can imagine some output formats dictating which fields are
  #    retrieved from the backend...)
  #
  #if args[api.PARAM_OUTPUT] not in ['html', 'tsv', 'csv', 'json', 'rss', 
  #  'rssdesc', 'xml', 'snippets_list']
  #
  # TODO: csv list of fields
  #if args[api.PARAM_FIELDS] not in ['all', 'rss']:

  # TODO: process dbg -- currently, anything goes...

  # RESERVED: v
  # RESERVED: sort
  # RESERVED: type

  def dbgargs(arg):
    logging.debug("args[%s]=%s" % (arg, args[arg]))

  if not api.PARAM_NUM in args:
    args[api.PARAM_NUM] = api.CONST_DFLT_NUM

  num = safe_int(args[api.PARAM_NUM], api.CONST_DFLT_NUM) 
  args[api.PARAM_NUM] = min_max(num, api.CONST_MIN_NUM, api.CONST_MAX_NUM)

  dbgargs(api.PARAM_NUM)

  if not api.PARAM_START in args:
    args[api.PARAM_START] = api.CONST_MIN_START
  else:
    args[api.PARAM_START] = min_max(
                safe_int(args[api.PARAM_START], api.CONST_MIN_START), 
                api.CONST_MIN_START, api.CONST_MAX_START - num)

  dbgargs(api.PARAM_START)
  
  if api.PARAM_OVERFETCH_RATIO in args:
    overfetch_ratio = float(args[api.PARAM_OVERFETCH_RATIO])
  elif args[api.PARAM_START] > 1:
    # increase the overfetch ratio after the first page--
    # overfetch is expensive and we don't want to do this
    # on page one, which is very performance sensitive.
    overfetch_ratio = api.CONST_MAX_OVERFETCH_RATIO
  else:
    overfetch_ratio = 2.0
  args[api.PARAM_OVERFETCH_RATIO] = min_max(
    overfetch_ratio, api.CONST_MIN_OVERFETCH_RATIO,
    api.CONST_MAX_OVERFETCH_RATIO)
  dbgargs(api.PARAM_OVERFETCH_RATIO)

  # PARAM_TIMEPERIOD overrides VOL_STARTDATE/VOL_ENDDATE
  if api.PARAM_TIMEPERIOD in args:
    period = args[api.PARAM_TIMEPERIOD]
    # No need to pass thru, just convert period to discrete date args.
    del args[api.PARAM_TIMEPERIOD]
    date_range = None
    today = datetime.date.today()
    if period == 'today':
      date_range = (today, today)
    elif period == 'this_weekend':
      days_to_sat = 5 - today.weekday()
      delta = datetime.timedelta(days=days_to_sat)
      this_saturday = today + delta
      this_sunday = this_saturday + datetime.timedelta(days=1)
      date_range = (this_saturday, this_sunday)
    elif period == 'this_week':
      days_to_mon = 0 - today.weekday()
      delta = datetime.timedelta(days=days_to_mon)
      this_monday = today + delta
      this_sunday = this_monday + datetime.timedelta(days=6)
      date_range = (this_monday, this_sunday)
    elif period == 'this_month':
      days_to_first = 1 - today.day
      delta = datetime.timedelta(days=days_to_first)
      first_of_month = today + delta
      days_to_month_end = calendar.monthrange(today.year, today.month)[1] - 1
      delta = datetime.timedelta(days=days_to_month_end)
      last_of_month = first_of_month + delta
      date_range = (first_of_month, last_of_month)

    if date_range:
      start_date = date_range[0].strftime("%Y-%m-%d")
      end_date = date_range[1].strftime("%Y-%m-%d")
      args[api.PARAM_VOL_STARTDATE] = start_date
      args[api.PARAM_VOL_ENDDATE] = end_date
      logging.debug("date range: "+ start_date + '...' + end_date)

  if api.PARAM_Q not in args:
    args[api.PARAM_Q] = ""
  else:
    args[api.PARAM_Q] = args[api.PARAM_Q].strip()
  dbgargs(api.PARAM_Q)

  if api.PARAM_VOL_LOC not in args or args[api.PARAM_VOL_LOC] == "":
    # bugfix for http://code.google.com/p/footprint2009dev/issues/detail?id=461
    # q=Massachusetts should imply vol_loc=Massachusetts, USA
    # note that this implementation also makes q=nature match
    # a town near santa ana, CA
    # http://www.allforgood.org/search#q=nature&vol_loc=nature%2C%20USA
    args[api.PARAM_VOL_LOC] = args[api.PARAM_Q] + " USA"

  args[api.PARAM_BACKFILL] = ""
  # First run query_rewriter classes
  args[api.PARAM_Q] = run_query_rewriters(args[api.PARAM_Q])
  # TODO: special hack for MLK day-- backfill with keywordless query
  # across the week
  logging.debug("q="+args[api.PARAM_Q]+" after reqrites")
  if args[api.PARAM_Q].find("category:MLK") >= 0:
    args[api.PARAM_BACKFILL] = api.PARAM_Q + "[]" + \
        ":"+api.PARAM_VOL_DIST + "[10]" + \
        ":"+api.PARAM_VOL_STARTDATE + "[2010-01-16]" + \
        ":"+api.PARAM_VOL_ENDDATE + "[2010-01-24]"
    logging.debug("found MLK query-- backfilling with keywordless 1/16-1/24: "+
                  args[api.PARAM_BACKFILL])

  args[api.PARAM_LAT] = args[api.PARAM_LNG] = ""
  if api.PARAM_VOL_LOC in args:
    zoom = 5
    if geocode.is_latlong(args[api.PARAM_VOL_LOC]):
      args[api.PARAM_LAT], args[api.PARAM_LNG] = \
                             args[api.PARAM_VOL_LOC].split(",")
    elif geocode.is_latlongzoom(args[api.PARAM_VOL_LOC]):
      args[api.PARAM_LAT], args[api.PARAM_LNG], zoom = \
                             args[api.PARAM_VOL_LOC].split(",")
    elif args[api.PARAM_VOL_LOC] == "virtual":
      args[api.PARAM_LAT] = args[api.PARAM_LNG] = "0.0"
      zoom = 6
    elif args[api.PARAM_VOL_LOC] == "anywhere":
      args[api.PARAM_LAT] = args[api.PARAM_LNG] = ""
    else:
      res = geocode.geocode(args[api.PARAM_VOL_LOC])
      if res != "":
        args[api.PARAM_LAT], args[api.PARAM_LNG], zoom = res.split(",")
    args[api.PARAM_LAT] = args[api.PARAM_LAT].strip()
    args[api.PARAM_LNG] = args[api.PARAM_LNG].strip()
    if api.PARAM_VOL_DIST in args:
      args[api.PARAM_VOL_DIST] = safe_int(args[api.PARAM_VOL_DIST])
    else:
      zoom = safe_int(zoom, 1)
      if zoom == 1:
        # country zoomlevel is kinda bogus--
        # 500 mile search radius (avoids 0.0,0.0 in the atlantic ocean)
        args[api.PARAM_VOL_DIST] = 500
      elif zoom == 2: # region
        # state/region is very wide-- start with 50 mile radius,
        # and we'll fallback to larger.
        args[api.PARAM_VOL_DIST] = 200
      elif zoom == 3: # county
        # county radius should be pretty rare-- start with 10 mile radius,
        # and we'll fallback to larger.
        args[api.PARAM_VOL_DIST] = 40
      elif zoom == 4 or zoom == 0:
        # city is the common case-- start with 5 mile search radius,
        # and we'll fallback to larger.  This avoids accidentally
        # prioritizing listings from neighboring cities.
        args[api.PARAM_VOL_DIST] = 35
      elif zoom == 5:
        # postal codes are also a common case-- start with a narrower
        # radius than the city, and we'll fallback to larger.
        args[api.PARAM_VOL_DIST] = 15
      elif zoom > 5:
        # street address or GPS coordinates-- start with a very narrow
        # search suitable for walking.
        args[api.PARAM_VOL_DIST] = 3

  else:
    args[api.PARAM_VOL_LOC] = args[api.PARAM_VOL_DIST] = ""
  dbgargs(api.PARAM_VOL_LOC)

def fetch_and_dedup(args):
  """fetch, score and dedup."""
  if api.PARAM_BACKEND_TYPE not in args:
    args[api.PARAM_BACKEND_TYPE] = api.BACKEND_TYPE_SOLR

  if args[api.PARAM_BACKEND_TYPE] == api.BACKEND_TYPE_BASE:
    logging.debug("Searching using BASE backend")
    result_set = base_search.search(args)
  elif args[api.PARAM_BACKEND_TYPE] == api.BACKEND_TYPE_SOLR:
    logging.debug("Searching using SOLR backend")
    result_set = solr_search.search(args)
  else:
    logging.error('search.fetch_and_dedup Unknown backend type: ' + 
                  args[api.PARAM_BACKEND_TYPE] +
                  ' defaulting to Base search')
    args[api.PARAM_BACKEND_TYPE] = api.BACKEND_TYPE_BASE
    result_set = base_search.search(args)

  scoring.score_results_set(result_set, args)

  merge_by_date_and_location = True
  if "key" in args:
    merge_by_date_and_location = False
    if api.PARAM_MERGE in args and args[api.PARAM_MERGE] == "1":
      merge_by_date_and_location = True
  result_set.dedup(merge_by_date_and_location)

  return result_set

class BackfillQuery(object):
  def __init__(self, args, bf_args, title = ''):
    # take the base query args as our defaults
    self.args = args
    self.title = title
   
    logging.debug("BackfillQuery: title '%s'" % (title))
    args_list = bf_args.split(BACKFILL_ARG_SEP)
    for arg in args_list:
      # we are given "param[value]" and we need to make it "param", "value"
      matchobj = re.match('(.+?)\[(.*?)\]', arg) 
      if matchobj:
        param_name = matchobj.group(1) 
        param_value = matchobj.group(2) 
      else: 
        param_name = arg
        param_value = "" 
      self.args[param_name] = param_value
      logging.debug("BackfillQuery: &%s=%s" % (param_name, param_value))


def fetch_result_set(args):
  """Validate the search parameters, and perform the search."""

  allow_virtual = False
  if api.PARAM_VIRTUAL in args and args[api.PARAM_VIRTUAL] == "1":
    allow_virtual = True

  def can_use_backfill(args, result_set):
    logging.debug("can_use_backfill: result_set.has_more_results="+
                  str(result_set.has_more_results)+
                  "  result_set.num_merged_results="+
                  str(result_set.num_merged_results))
    if (not result_set.has_more_results
        and result_set.num_merged_results <
        (safe_int(args[api.PARAM_NUM], api.CONST_DFLT_NUM) + 
         safe_int(args[api.PARAM_START], api.CONST_MIN_START))):
      return True
    return False

  result_set = fetch_and_dedup(args)

  if can_use_backfill(args, result_set):
    backfill_num = 0
    if api.PARAM_BACKFILL in args and args[api.PARAM_BACKFILL] != "":
      logging.debug("parsing backfill query args: &bfq="+
                    args[api.PARAM_BACKFILL])
      # parse backfill args-- &bf (queries) and &bft (titles)
      bfq_list = []
      backfills_list = args[api.PARAM_BACKFILL].split(BACKFILL_QUERY_SEP)
      backfill_titles_list = []
      if (api.PARAM_BACKFILL_TITLES in args and 
          args[api.PARAM_BACKFILL_TITLES] != ""):
        backfill_titles_list = args[api.PARAM_BACKFILL_TITLES].split(
          BACKFILL_QUERY_SEP)
  
      for idx, bfq_args in enumerate(backfills_list):
        bf_title = ""
        if (idx < len(backfill_titles_list) and 
            len(backfill_titles_list[idx]) > 0):
          bf_title = backfill_titles_list[idx]
        bfq = BackfillQuery(args, bfq_args, bf_title)
        # we dont want to recurse ad infinitum
        bfq.args['bf'] = bfq.args['bft'] = ''
        bfq_list.append(bfq)

      for bfq in bfq_list:
        backfill_num += 1
        #logging.debug("BackfillQuery: i=%d  '%s' => %s" %
        #              (backfill_num, bfq.title, bfq.args))
        bf_res = fetch_and_dedup(bfq.args)
        for res in bf_res.merged_results:
          res.backfill_title = bfq.title
          res.backfill_number = backfill_num
          #logging.info("BackfillQuery %d: %s with %s" % 
          #             (res.backfill_number, bfq.title, res.title))
        result_set.append_results(bf_res)

    # backfill with locationless listings
    if allow_virtual and (args[api.PARAM_LAT] != "0.0" or args[api.PARAM_LNG] != "0.0"):
      backfill_num += 1
      newargs = copy.copy(args)
      newargs[api.PARAM_LAT] = newargs[api.PARAM_LNG] = "0.0"
      newargs[api.PARAM_VOL_DIST] = 50
      logging.debug("backfilling with locationless listings...")
      locationless_result_set = fetch_and_dedup(newargs)
      for res in locationless_result_set.merged_results:
        res.backfill_title = "locationless (virtual) listings"
        res.backfill_number = backfill_num
      old_len = len(result_set.results)
      result_set.append_results(locationless_result_set)
      logging.debug("#results=%d  #locationless=%d = new #results=%d" %
                    (old_len, len(locationless_result_set.results),
                    len(result_set.results)))
  return result_set
