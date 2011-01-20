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
toss all the scoring code into one place (rather than a class file)
because scoring tends to get complex quickly.
"""

from datetime import datetime
import logging
import math
import api

import view_helper

def compare_scores(val1, val2):
  """helper function for sorting."""
  diff = val2.score - val1.score
  if (diff > 0):
    return 1
  if (diff < 0):
    return -1
  return 0

def score_results_set(result_set, args):
  """sort results by score, and for each, set .score, .scorestr, .score_notes"""
  logging.debug(str(datetime.now())+": score_results_set(): start")
  idlist = map(lambda x: x.item_id, result_set.results)
  # handle rescoring on interest weights
  others_interests = view_helper.get_interest_for_opportunities(idlist)
  total_results = float(len(result_set.results))
  for i, res in enumerate(result_set.results):
    score = 1.0
    score_notes = ""

    # keywordless queries should rank by location and time, not relevance.
    if api.PARAM_Q in args and args[api.PARAM_Q] != "":
      # lower ranking items in the backend = lower ranking here (roughly 1/rank)
      rank_mult = float(total_results - i)/float(total_results)
      score *= rank_mult
      score_notes += "  backend multiplier=%.3f (rank=%d)\n" % (rank_mult, i+1)

    # boost vetted listings
    if 'Vetted' in res.all_categories:
      vetted_mult = 10.0
      score *= vetted_mult
      score_notes += "  vetted listing: mult=%.3f\n" % (vetted_mult)

    if 'MLK' in res.all_categories:
      # blood drives and date ranges are included in the MLK category 
      # so if has mlk or martin luther, bump it up
      text = (res.title + ' ' + res.snippet).lower()
      if text.find('mlk') >=0 or text.find('martin luther') >=0:
        mlk_mult = 5.0
        score *= mlk_mult
        score_notes += "  mlk fix: mult=%.3f\n" % (mlk_mult)

    # TODO: match on start time, etc.

    ONEDAY = 24.0 * 3600.0
    MAXTIME = 500.0 * ONEDAY
    start_delta = res.startdate - datetime.now()
    start_delta_days = start_delta.days + (start_delta.seconds / 86400.0)
    if start_delta_days > 60.0:
      if start_delta_days > 359.0:
        start_delta_days = 359.0
      # big penalty for events starting in the far future
      start_delta_days_mult = 0.5 * (360.0 - start_delta_days) / 360.0
    elif start_delta_days > 0.0:
      # big boost for events starting in the near future
      start_delta_days_mult = (360.0 - start_delta_days) / 360.0
    elif start_delta_days > -30:
      # slight penalty for events started recently
      start_delta_days_mult = 0.9 * (360.0 + start_delta_days) / 360.0
    else:
      if start_delta_days < -359.0:
        start_delta_days = -359.0
      # modest penalty for events started long ago
      start_delta_days_mult = 0.7 * (360.0 + start_delta_days) / 360.0
    score *= start_delta_days_mult
    score_notes += "  start_mult=" + str(start_delta_days_mult)
    score_notes += " (%s  %g days)" % (str(res.startdate), start_delta_days)

    end_delta = res.enddate - datetime.now()
    end_delta_days = end_delta.days + (end_delta.seconds / 86400.0)
    if end_delta_days > 60:
      if end_delta_days > 359:
        end_delta_days = 359
      # modest penalty for events ending in the far future
      end_delta_days_mult = 0.9 * (360 - end_delta_days) / 360
    elif end_delta_days > 0:
      # big boost for events ending in the near future
      end_delta_days_mult = (360 - end_delta_days) / 360
    else:
      # shouldn't happen
      end_delta_days_mult = 0.0
    score *= end_delta_days_mult
    score_notes += "  end_mult=" + str(end_delta_days_mult)
    score_notes += " (%s  %g days)" % (str(res.enddate), end_delta_days)
    score_notes += "\n"

    # boost short events
    delta_secs = (end_delta_days - start_delta_days) * 86400.0
    if delta_secs > 0:
      # up to 14 days gets a boost
      ddays = 10*max(14 - delta_secs/ONEDAY, 1.0)
      date_delta_multiplier = math.log10(ddays)
    else:
      date_delta_multiplier = 1
    score *= date_delta_multiplier
    score_notes += "  date_delta_mult=%.3f (%g days)\n" % (
      date_delta_multiplier, delta_secs / float(ONEDAY))

    if ((api.PARAM_LAT not in args) or args[api.PARAM_LAT] == "" or
        (api.PARAM_LNG not in args) or args[api.PARAM_LNG] == "" or
         res.latlong == ""):
      geo_dist_multiplier = 0.5
    else:
      # TODO: error in the DB, we're getting same geocodes for everything
      lat, lng = res.latlong.split(",")
      latdist = float(lat) - float(args[api.PARAM_LAT])
      lngdist = float(lng) - float(args[api.PARAM_LNG])
      # keep one value to right of decimal
      delta_dist = latdist*latdist + lngdist*lngdist
      logging.debug("qloc=%s,%s - listing=%g,%g - dist=%g,%g - delta = %g" %
             (args[api.PARAM_LAT], args[api.PARAM_LNG], float(lat), float(lng),
              latdist, lngdist, delta_dist))
      # reasonably local
      if delta_dist <= 0.025:
        geo_dist_multiplier = 1.0 - delta_dist
      else:
        geo_dist_multiplier = 0.5 - delta_dist*delta_dist
      if geo_dist_multiplier < 0.01:
        geo_dist_multiplier = 0.01

    interest = -1
    if res.item_id in others_interests:
      interest = others_interests[res.item_id]
    elif "test_stars" in args:
      interest = i % 6

    score *= geo_dist_multiplier
    score_notes += "  geo multiplier=" + str(geo_dist_multiplier)

    if interest >= 0:
      # TODO: remove hocus-pocus math
      interest_weight = (math.log(interest+1.0)/math.log(6.0))**3
      score *= interest_weight
      score_notes += "  "+str(interest)+"-stars="+str(interest_weight)

    res.set_score(score, score_notes)

  result_set.results.sort(cmp=compare_scores)
  logging.debug(str(datetime.now())+": score_results_set(): done")

