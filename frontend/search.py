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

from google.appengine.api import memcache

import api
import base_search
import geocode
import scoring
from fastpageviews import pagecount

CACHE_TIME = 24*60*60  # seconds

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
  start = int(args[api.PARAM_START])
  num = int(args[api.PARAM_NUM])

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


def normalize_query_values(args):
  """Pre-processes several values related to the search API that might be
  present in the query string."""

  num = 10
  if api.PARAM_NUM in args:
    num = int(args[api.PARAM_NUM])
    if num < 1:
      num = 1
    if num > 999:
      num = 999
  args[api.PARAM_NUM] = num

  start_index = 1
  if api.PARAM_START in args:
    start_index = int(args[api.PARAM_START])
    if start_index < 1:
      start_index = 1
    if start_index > 1000-num:
      start_index = 1000-num
  args[api.PARAM_START] = start_index

  overfetch_ratio = 2.0
  if api.PARAM_OVERFETCH_RATIO in args:
    overfetch_ratio = float(args[api.PARAM_OVERFETCH_RATIO])
    if overfetch_ratio < 1.0:
      overfetch_ratio = 1.0
    if overfetch_ratio > 10.0:
      overfetch_ratio = 10.0
  args[api.PARAM_OVERFETCH_RATIO] = overfetch_ratio

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


def fetch_result_set(args):
  """Validate the search parameters, and perform the search."""
  if api.PARAM_Q not in args:
    args[api.PARAM_Q] = ""

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

  args["lat"] = args["long"] = ""
  if api.PARAM_VOL_LOC in args:
    zoom = 5
    if geocode.is_latlong(args[api.PARAM_VOL_LOC]):
      args["lat"], args["long"] = args[api.PARAM_VOL_LOC].split(",")
    elif geocode.is_latlongzoom(args[api.PARAM_VOL_LOC]):
      args["lat"], args["long"], zoom = args[api.PARAM_VOL_LOC].split(",")
    else:
      res = geocode.geocode(args[api.PARAM_VOL_LOC])
      if res != "":
        args["lat"], args["long"], zoom = res.split(",")
    args["lat"] = args["lat"].strip()
    args["long"] = args["long"].strip()
    if api.PARAM_VOL_DIST not in args:
      zoom = int(zoom)
      if zoom == 1: # country
        args[api.PARAM_VOL_DIST] = 500
      elif zoom == 2: # region
        args[api.PARAM_VOL_DIST] = 300
      elif zoom == 3: # county
        args[api.PARAM_VOL_DIST] = 100
      elif zoom == 4 or zoom == 0: # city/town
        args[api.PARAM_VOL_DIST] = 50
      elif zoom == 5: # postal code
        args[api.PARAM_VOL_DIST] = 25
      elif zoom > 5: # street or level
        args[api.PARAM_VOL_DIST] = 10
  else:
    args[api.PARAM_VOL_LOC] = args[api.PARAM_VOL_DIST] = ""

  result_set = base_search.search(args)
  scoring.score_results_set(result_set, args)
  result_set.dedup()

  if (not result_set.has_more_results 
      and result_set.num_merged_results < int(args[api.PARAM_NUM])
      and result_set.estimated_merged_results >= int(args[api.PARAM_NUM])
      and float(args[api.PARAM_OVERFETCH_RATIO]) < api.CONST_MAX_OVERFETCH_RATIO):
    # Note: recursion terminated by value of overfetch >= api.CONST_MAX_OVERFETCH_RATIO
    args[api.PARAM_OVERFETCH_RATIO] = api.CONST_MAX_OVERFETCH_RATIO
    logging.info("requery with overfetch=%d" % args[api.PARAM_OVERFETCH_RATIO]) 
    # requery now w/ max overfetch_ratio
    result_set = fetch_result_set(args)

  return result_set
