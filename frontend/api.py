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
API query parameters.  Defined here as symbolic constants to ensure
typos become compile-time errors.
"""

PARAM_NUM = 'num'
CONST_MIN_NUM = 1
CONST_MAX_NUM = 999
CONST_DFLT_NUM = 10

PARAM_START = 'start'
CONST_MIN_START = 1
CONST_MAX_START = 1000

BACKEND_TYPE_BASE = 'backend_type_base'
BACKEND_TYPE_SOLR = 'backend_type_solr'

PARAM_BACKEND_TYPE = 'backend_type'
PARAM_BACKEND_URL = 'backend_url'
PARAM_OUTPUT = 'output'
PARAM_Q = 'q'
PARAM_SORT = 'sort'
PARAM_CACHE = 'cache'
PARAM_FIELDS = 'fields'
PARAM_CAMPAIGN_ID = 'campaign_id'

# If PARAM_OUTPUT matches one of these entries, only certain fields will be
# returned. Otherwise, all fields are returned.
FIELDS_BY_OUTPUT_TYPE = {'html' :
                           'abstract,' + \
                           'categories,org_name,' + \
                           'detailurl,' + \
                           'event_date_range,' + \
                           'feed_providername,' + \
                           'id,' + \
                           'latitude,' + \
                           'location_string,' + \
                           'longitude,' + \
                           'title'
                           }
# Fielts to be returned when PARAM_OUTPUT is not set.
# TODO: remove this once all output types have been specified.
DEFAULT_OUTPUT_FIELDS = FIELDS_BY_OUTPUT_TYPE['html']

# E.g., 'today'. The presence of this param implies that 'vol_startdate'
# and 'vol_enddate' will be automatically calculated, overriding
# the values of those two params if they were passed in also.
PARAM_TIMEPERIOD = 'timeperiod'

# the ratio of actual results to request from the backend--
# typical values range from 1.0 to 10.0, where larger numbers
# provide better quality results at a linear incease in latency
# This internal value is exposed as an URL parameter so we can
# run performance tests, please email engineering before using
# this in apps, so we don't change it later.
PARAM_OVERFETCH_RATIO = 'overfetch'
# TODO: define other constants in api.py, eg...
CONST_MIN_OVERFETCH_RATIO = 1.0
CONST_MAX_OVERFETCH_RATIO = 10.0
CONST_MAX_FETCH_DEADLINE = 10

PARAM_VOL_LOC = 'vol_loc'
PARAM_VOL_DIST = 'vol_dist'
PARAM_VOL_STARTDATE = 'vol_startdate'
PARAM_VOL_ENDDATE = 'vol_enddate'
PARAM_VOL_DURATION = 'vol_duration'
PARAM_VOL_INCLUSIVEDATES = 'vol_inclusivedates'
PARAM_VOL_TZ = 'vol_tz'
PARAM_VOL_PROVIDER = 'vol_provider'
PARAM_VOL_STARTDAYOFWEEK = 'vol_startdayofweek'

PARAM_BACKFILL = 'bf'
PARAM_BACKFILL_TITLES = 'bft'

PARAM_LAT = 'lat'
PARAM_LNG = 'long'
