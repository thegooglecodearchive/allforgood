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

PARAM_FIELDS = 'fields'
PARAM_NUM = 'num'
PARAM_OUTPUT = 'output'
PARAM_Q = 'q'
PARAM_SORT = 'sort'
PARAM_START = 'start'
PARAM_CACHE = 'cache'
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
CONST_MAX_OVERFETCH_RATIO = 10.0
CONST_MAX_FETCH_DEADLINE = 10

PARAM_VOL_LOC = 'vol_loc'
PARAM_VOL_DIST = 'vol_dist'
PARAM_VOL_STARTDATE = 'vol_startdate'
PARAM_VOL_ENDDATE = 'vol_enddate'
PARAM_VOL_DURATION = 'vol_duration'
PARAM_VOL_TZ = 'vol_tz'
PARAM_VOL_PROVIDER = 'vol_provider'
PARAM_VOL_STARTDAYOFWEEK = 'vol_startdayofweek'
