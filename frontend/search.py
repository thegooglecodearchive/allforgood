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
import pickle

#from versioned_memcache import memcache
from google.appengine.api import memcache
from utils import safe_str, safe_int

import api
import geocode_mapsV3 as geocode
import solr_search
import re

from google.appengine.ext import db

from query_rewriter import get_rewriters

CACHE_TIME = 24*60*60  # seconds
MAX_CACHE_SZ = (1000000) - 1

class CacheUpdate(db.Model):
  updated = db.DateTimeProperty(auto_now = True)


def update_cache_key():
  """ """
  try:
    rec = CacheUpdate.get_or_insert('search')
    rec.put()
  except:
    logging.warning("update_cache_key failed")


def get_cache_key(normalized_query_string, chunk = 0):
  """ """

  rtn = 'search:' + normalized_query_string
  rec = CacheUpdate.get_by_key_name('search')
  if rec:
    rtn += str(rec.updated)

  return 'chu' + str(chunk) + ':' + hashlib.md5(rtn).hexdigest()


def run_query_rewriters(query):
  rewriters = get_rewriters()
  query = rewriters.rewrite_query(query)
  return query

# args is expected to be a list of args
# and any path info is supposed to be homogenized into this,
# e.g. /listing/56_foo should be resolved into [('id',56)]
# by convention, repeated args are ignored, LAST ONE wins.
def search(args, dumping = False):
  logging.info("search.search enter")
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
  
  normalize_query_values(args, dumping)

  # TODO: query param (& add to spec) for defeating the cache (incl FastNet)
  # I (mblain) suggest using "zx", which is used at Google for most services.

  # TODO: Should construct our own normalized query string instead of
  # using the browser's querystring.

  args_array = [str(key)+'='+str(value) for (key, value) in args.items()]
  args_array.sort()
  normalized_query_string = str('&'.join(args_array))
  logging.info('normalized_query_string: ' + normalized_query_string)

  use_cache = False
  if api.PARAM_CACHE in args and args[api.PARAM_CACHE] == '0':
    use_cache = False
    logging.debug('Not using search cache')

  start = safe_int(args[api.PARAM_START], api.CONST_MIN_START)
  num = safe_int(args[api.PARAM_NUM], api.CONST_DFLT_NUM)

  result_set = None
  # note: key cannot exceed 250 bytes
  #memcache_key = get_cache_key(normalized_query_string)

  if use_cache:
    result_set_str = ''
    chunk = 0
    while True:
      logging.info(get_cache_key(normalized_query_string, chunk))
      buff = memcache.get(get_cache_key(normalized_query_string, chunk))
      if not buff:
        break
      result_set_str += buff
      chunk += 1

    if result_set_str:
      try:
        result_set = pickle.loads(result_set_str)
      except:
        logging.warning('result_set not completely in cache')
        pass

    if result_set:
      logging.debug('in cache: "' + normalized_query_string + '"')
      if len(result_set.merged_results) < start + num:
        logging.debug('but too small-- rerunning query...')
        result_set = None
    else:
      logging.debug('not in cache: "' + normalized_query_string + '"')

  if not result_set:
    result_set = fetch_result_set(args, dumping)
    if result_set:
      result_set_str = pickle.dumps(result_set)
      sz = len(result_set_str)
      chunk = idx = 0
      while sz > 0:
        buff = result_set_str[idx:idx + MAX_CACHE_SZ]
        memcache.set(get_cache_key(normalized_query_string, chunk), buff, time=CACHE_TIME)
        sz -= MAX_CACHE_SZ
        idx += MAX_CACHE_SZ
        chunk += 1

  logging.info('result_set size after dedup: ' + str(result_set.num_merged_results))

  result_set.clip_merged_results(start, num)
  logging.info("search.search clip_merged_results completed")

  return result_set

def min_max(val, minval, maxval):
  return max(min(maxval, val), minval)

def normalize_query_values(args, dumping = False):
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

  if not dumping:
    if not api.PARAM_START in args:
      args[api.PARAM_START] = api.CONST_MIN_START
    else:
      args[api.PARAM_START] = min_max(
                safe_int(args[api.PARAM_START], api.CONST_MIN_START), 
                api.CONST_MIN_START, api.CONST_MAX_START - num)

  dbgargs(api.PARAM_START)
  
  if dumping:
      overfetch_ratio = 1.0
  else:
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

  use_cache = True
  if api.PARAM_CACHE in args and args[api.PARAM_CACHE] == '0':
    use_cache = False
    logging.debug('Not using search cache')

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
      start_date = date_range[0].strftime("%m/%d/%Y")
      end_date = date_range[1].strftime("%m/%d/%Y")
      args[api.PARAM_VOL_STARTDATE] = start_date
      args[api.PARAM_VOL_ENDDATE] = end_date

  if api.PARAM_TIMEPERIOD_START in args and args[api.PARAM_TIMEPERIOD_START] == 'start date':
    del args[api.PARAM_TIMEPERIOD_START]

  if api.PARAM_TIMEPERIOD_END in args and args[api.PARAM_TIMEPERIOD_END] == 'end date':
    del args[api.PARAM_TIMEPERIOD_END]

  if api.PARAM_TIMEPERIOD_START in args and api.PARAM_TIMEPERIOD_END in args and (api.PARAM_TIMEPERIOD not in args):
      start_date = args[api.PARAM_TIMEPERIOD_START]
      end_date = args[api.PARAM_TIMEPERIOD_END]
      args[api.PARAM_VOL_STARTDATE] = start_date
      args[api.PARAM_VOL_ENDDATE] = end_date

  if api.PARAM_Q not in args:
    args[api.PARAM_Q] = ""
  else:
    args[api.PARAM_Q] = args[api.PARAM_Q].strip()
  dbgargs(api.PARAM_Q)

  if (api.PARAM_VOL_LOC not in args 
      or args[api.PARAM_VOL_LOC] == ""
      or args[api.PARAM_VOL_LOC].lower().find("location") >=0
     ):
    # bugfix for http://code.google.com/p/footprint2009dev/issues/detail?id=461
    # q=Massachusetts should imply vol_loc=Massachusetts, USA
    # note that this implementation also makes q=nature match
    # a town near santa ana, CA
    # http://www.allforgood.org/search#q=nature&vol_loc=nature%2C%20USA
    # args[api.PARAM_VOL_LOC] = args[api.PARAM_Q] + " USA"
    # MT: 8/26/2010 - in practice that causes a lot of 602 results in geocode, eg "Laywers, USA"
    args[api.PARAM_VOL_LOC] = "USA"

  args[api.PARAM_LAT] = args[api.PARAM_LNG] = ""
  if api.PARAM_VIRTUAL in args:
    args["lat"] = args["long"] = "0.0"
    args[api.PARAM_VOL_DIST] = 25
    
  elif api.PARAM_VOL_LOC in args:
    if geocode.is_latlong(args[api.PARAM_VOL_LOC]):
      args[api.PARAM_LAT], args[api.PARAM_LNG] = \
                             args[api.PARAM_VOL_LOC].split(",")
    elif geocode.is_latlongzoom(args[api.PARAM_VOL_LOC]):
      args[api.PARAM_LAT], args[api.PARAM_LNG], zoom = \
                             args[api.PARAM_VOL_LOC].split(",")
    elif args[api.PARAM_VOL_LOC] == "virtual":
      args[api.PARAM_LAT] = args[api.PARAM_LNG] = "0.0"
    elif args[api.PARAM_VOL_LOC] == "anywhere":
      args[api.PARAM_LAT] = args[api.PARAM_LNG] = ""
    else:
      res = geocode.geocode(args[api.PARAM_VOL_LOC], use_cache)
      if res != "":
        args[api.PARAM_LAT], args[api.PARAM_LNG], zoom = res.split(",")
    
    args[api.PARAM_LAT] = args[api.PARAM_LAT].strip()
    args[api.PARAM_LNG] = args[api.PARAM_LNG].strip()    
    if api.PARAM_DISTANCE in args:
      args[api.PARAM_VOL_DIST] = safe_int(args[api.PARAM_DISTANCE])
    else:
      if api.PARAM_VOL_DIST in args:
          args[api.PARAM_VOL_DIST] = safe_int(args[api.PARAM_VOL_DIST])
      else:
          args[api.PARAM_VOL_DIST] = 25

  else:
    args[api.PARAM_VOL_LOC] = args[api.PARAM_VOL_DIST] = ""
  dbgargs(api.PARAM_VOL_LOC)

def fetch_and_dedup(args, dumping = False):
  """fetch, score and dedup."""
  logging.info("search.fetch_and_dedup enter")
  result_set = solr_search.search(args, dumping)

  if dumping:
    result_set.merged_results = result_set.results
    for idx, result in enumerate(result_set.merged_results):
      result_set.merged_results[idx].merge_key = ''
      result_set.merged_results[idx].merged_list = []
      result_set.merged_results[idx].merged_debug = []
  else:
    merge_by_date_and_location = True
    if "key" in args:
      merge_by_date_and_location = False
      if api.PARAM_MERGE in args and args[api.PARAM_MERGE] == "1":
        merge_by_date_and_location = True
    result_set.dedup(merge_by_date_and_location)

  return result_set

def fetch_result_set(args, dumping = False):
  """Validate the search parameters, and perform the search."""
  logging.info("search.fetch_result_set enter")

  allow_virtual = False
  if api.PARAM_VIRTUAL in args and args[api.PARAM_VIRTUAL] == "1":
    allow_virtual = True

  result_set = fetch_and_dedup(args, dumping)
  return result_set
