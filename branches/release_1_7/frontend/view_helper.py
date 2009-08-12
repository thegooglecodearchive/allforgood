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
Utilities that support views.py.
"""

import logging
import models
import modelutils

from django.utils import simplejson

def get_user_interests(user, remove_no_interest):
  """Get the opportunities a user has expressed interest in.

  Args:
    user: userinfo.User of a user
    remove_no_interest: Filter out items with no expressed interest.
  Returns:
    Dictionary of volunteer opportunity id: expressed interest (liked).
  """
  user_interests = {}
  if user:
    user_info = user.get_user_info()
    # Note: If we want a limit, tack "fetch(nnn)" on the end of the query.
    # Also note the descending order, most-recent-first.

    interests = models.UserInterest.all().filter('user = ', user_info)\
                .order('-liked_last_modified')
    #interests = models.UserInterest.all().filter('user = ', user_info)

    ordered_event_ids = []
    for interest in interests:
      interest_value = getattr(interest, models.USER_INTEREST_LIKED)
      if not remove_no_interest or interest_value != 0:
        user_interests[interest.opp_id] = interest_value
        ordered_event_ids.append(interest.opp_id)

  return (user_interests, ordered_event_ids)


def get_interest_for_opportunities(opp_ids):
  """Get the interest statistics for a set of volunteer opportunities.

  Args:
    opp_ids: list of volunteer opportunity ids.

  Returns:
    Dictionary of volunteer opportunity id: aggregated interest values.
  """
  others_interests = {}

  interests = modelutils.get_by_ids(models.VolunteerOpportunityStats, opp_ids)
  for (item_id, interest) in interests.iteritems():
    if interest:
      others_interests[item_id] = getattr(interest, models.USER_INTEREST_LIKED)
  return others_interests


def get_annotated_results(user, result_set):
  """Get results annotated with the interests of this user and all users.

  Args:
    user: User object returned by userinfo.get_user()
    result_set: A search.SearchResultSet.
  Returns:
    The incoming result set, annotated with user-specific info.
  """

  # Get all the ids of items we've found
  opp_ids = [result.item_id for result in result_set.results]

  # mark the items the user is interested in
  (user_interests, ordered_event_ids) = get_user_interests(user, True)

  # note the interest of others
  others_interests = get_interest_for_opportunities(opp_ids)

  return annotate_results(user_interests, others_interests, result_set)


def annotate_results(user_interests, others_interests, result_set):
  """Annotates results with the provided interests.

  Args:
    user_interests: User interests from get_user_interests. Can be None.
    others_interests: Others interests from get_interest_for_opportunities.
                      Can be None.
    result_set: A search.SearchResultSet.
  Returns:
    The incoming result set, annotated with user-specific info.
  """

  # Mark up the results
  for result in result_set.results:
    if user_interests and result.item_id in user_interests:
      result.interest = user_interests[result.item_id]
    if others_interests and result.item_id in others_interests:
      logging.debug("others interest in %s = %s " %
                    (result.item_id, others_interests[result.item_id]))
      # TODO: Consider updating the base url here if it's changed.
      result.interest_count = others_interests[result.item_id]

  return result_set


def get_friends_data_for_snippets(user_info):
  """Preps the data required to render the "My Events" aka "Profile" template.
  Args:
    user_info: userinfo.User for the current user.
  Returns:
    Dictionary of data required to render the template.
  """

  # Get the list of all my friends.
  # Assemble the opportunities your friends have starred.
  friends = user_info.load_friends()
  
  # For each of my friends, get the list of all events that that friend likes
  # or is doing.
  # For each of the events found, cross-reference the list of its interested
  # users.
  friend_opp_count = {}
  friends_by_event_id = {}
  for friend in friends:
    (user_interests, ordered_event_ids) = get_user_interests(friend, True)
    for event_id in user_interests:
      count = friend_opp_count.get(event_id, 0)
      friend_opp_count[event_id] = count + 1
      uids = friends_by_event_id.get(event_id, [])
      uids.append(friend.user_id)
      friends_by_event_id[event_id] = uids

  friends_by_event_id_js = simplejson.dumps(friends_by_event_id)

  view_vals = {
    'friends': friends,
    'friends_by_event_id_js': friends_by_event_id_js,
  }

  return view_vals
