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

    # TODO: match on start time, etc.

    ONEDAY = 24.0 * 3600.0
    MAXTIME = 500.0 * ONEDAY
    start_delta = res.startdate - datetime.now()
    start_delta_secs = start_delta.days*ONEDAY + start_delta.seconds
    start_delta_secs = min(max(start_delta_secs, 0), MAXTIME)
    end_delta = res.enddate - datetime.now()
    end_delta_secs = end_delta.days*ONEDAY + end_delta.seconds
    end_delta_secs = min(max(end_delta_secs, start_delta_secs), MAXTIME)
    date_dist_multiplier = 1
    if end_delta_secs <= 0:
      date_dist_multiplier = .0001
    if start_delta_secs > 0:
      # further out start date = lower rank (roughly 1/numdays)
      date_dist_multiplier = 1.0/(start_delta_secs/ONEDAY)

    score *= date_dist_multiplier
    score_notes += "  date_mult=" + str(date_dist_multiplier)
    score_notes += "  start=%s (%+g days)" % (
      res.startdate, start_delta_secs / ONEDAY)
    score_notes += "  end=%s (%+g days)" % (
      res.enddate, end_delta_secs / ONEDAY)
    score_notes += "\n"

    # boost short events
    delta_secs = end_delta_secs - start_delta_secs
    if delta_secs > 0:
      # up to 14 days gets a boost
      ddays = 10*max(14 - delta_secs/ONEDAY, 1.0)
      date_delta_multiplier = math.log10(ddays)
    else:
      date_delta_multiplier = 1
    score *= date_delta_multiplier
    score_notes += "  date_delta_mult=%.3f (%g days)\n" % (
      date_delta_multiplier, delta_secs / float(ONEDAY))

    if (("lat" not in args) or args["lat"] == "" or
        ("long" not in args) or args["long"] == "" or
         res.latlong == ""):
      geo_dist_multiplier = 0.5
    else:
      # TODO: error in the DB, we're getting same geocodes for everything
      lat, lng = res.latlong.split(",")
      latdist = float(lat) - float(args["lat"])
      lngdist = float(lng) - float(args["long"])
      # keep one value to right of decimal
      delta_dist = latdist*latdist + lngdist*lngdist
      logging.debug("qloc=%s,%s - listing=%g,%g - dist=%g,%g - delta = %g" %
                   (args["lat"], args["long"], float(lat), float(lng),
                    latdist, lngdist, delta_dist))
      # reasonably local
      if delta_dist > 0.025:
        delta_dist = 0.9 + delta_dist
      else:
        delta_dist = delta_dist / (0.025 / 0.9)
      if delta_dist > 0.999:
        delta_dist = 0.999
      geo_dist_multiplier = 1.0 - delta_dist

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

