#!/usr/bin/python2.5
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

"""Datastore models."""

from google.appengine.api import memcache
from google.appengine.ext import db

import modelutils

class Error(Exception):
  """Generic error."""
  pass

class BadAccountType(Error):
  """Account type is unknown (not facebook, friendconnect, or test)."""
  pass


# Models

class UserInfo(db.Model):
  """Basic user statistics/preferences data."""
  # Key is accounttype:user_id.
  first_visit = db.DateTimeProperty(auto_now_add=True)
  last_edit = db.DateTimeProperty(auto_now=True)
  moderator = db.BooleanProperty(default=False)
  moderator_request_email = db.StringProperty()
  moderator_request_desc = db.TextProperty()
  moderator_request_admin_notes = db.StringProperty(multiline=True)

  def account_type(self):
    """Returns one of (FRIENDCONNECT, FACEBOOK, TEST)."""
    key_name = self.key().name()
    return key_name.split(':', 1)[0]

  def user_id(self):
    """User id."""
    key_name = self.key().name()
    return key_name.split(':', 1)[1]

  # Known types of accounts. Type must not start with a number.
  FRIENDCONNECT = 'friendconnect'
  FACEBOOK = 'facebook'
  TEST = 'test'
  KNOWN_TYPES = (FRIENDCONNECT, FACEBOOK, TEST)

  @classmethod
  def get_or_insert_user(cls, account_type, user_id):
    """Gets existing or creates a new user.

    Similar to get_or_insert, increments UserStats if appropriate.

    Args:
      account_type: Type of account used.
      user_id: address within that system.

    Returns:
      UserInfo for this user.

    Raises:
      BadAccountType if the account_type is unknown.
      Various datastore exceptions.
    """
    if not account_type in cls.KNOWN_TYPES:
      raise BadAccountType()

    key_name = '%s:%s' % (account_type, user_id)
    user_info = cls.get_by_key_name(key_name)

    def txn():
      """Transaction to get or insert user."""
      entity = cls.get_by_key_name(key_name)
      created_entity = False
      if entity is None:
        entity = cls(key_name=key_name)
        entity.put()
        created_entity = True
      return (entity, created_entity)

    (user_info, created_entity) = db.run_in_transaction(txn)

    if created_entity:
      UserStats.increment(account_type, user_id)

    return user_info


class UserStats(db.Model):
  """Stats about how many users we have."""
  count = db.IntegerProperty(default=0)

  @classmethod
  def increment(cls, account_type, user_id):
    """Sharded counter. User ID is only for sharding."""
    def txn():
      """Transaction to increment account_type's stats."""
      # We want << 1000 shards.
      # This cheesy shard mechanism allows us some amount of way to see how
      # many users of each type we have too.
      shard_name = account_type + ':' + user_id[:2]
      counter = cls.get_by_key_name(shard_name)
      if not counter:
        counter = cls(key_name=shard_name)
      counter.count += 1
      counter.put()

    db.run_in_transaction(txn)

  @staticmethod
  def get_count():
    """Returns total number of users."""
    total = 0
    for counter in UserStats.all():
      total += counter.count
    return total


class UserInterest(db.Model):
  """Our record a user's actions related to an opportunity."""
  # Key is ('id:%s#%s' % (the stable ID from base, user key name))
  # stable ID is probabaly not the same ID provided in the feed from providers.
  DATASTORE_PREFIX = 'id:'
  user = db.ReferenceProperty(UserInfo, collection_name='interests')
  opp_id = db.StringProperty()
  liked_last_modified = db.DateTimeProperty()

  # The interest types (liked, will_attend, etc) must exist with the
  # same property names in UserInterest and VolunteerOpportunityStats,
  # and be in sync with USER_INTEREST_ATTRIBUTES at the end of this file.
  liked = db.IntegerProperty(default=0)
  will_attend = db.IntegerProperty(default=0)
  flagged = db.IntegerProperty(default=0)

  @classmethod
  def make_key_name(cls, user_entity, opp_id):
    """Generate key name for a given user_entity/opp_id pair."""
    return '%s:%s#%s' % (cls.DATASTORE_PREFIX, opp_id, user_entity.key().name())


class VolunteerOpportunityStats(db.Model):
  """Basic statistics about opportunities."""
  # The __key__ is 'id:' + volunteer_opportunity_id
  DATASTORE_PREFIX = 'id:'
  MEMCACHE_PREFIX = 'VolunteerOpportunityStats:'
  MEMCACHE_TIME = 60000  # seconds
  last_edit = db.DateTimeProperty(auto_now=True)

  # The interest types (liked, will_attend, etc) must exist with the
  # same property names in UserInterest and VolunteerOpportunityStats,
  # and be in sync with USER_INTEREST_ATTRIBUTES at the end of this file.
  liked = db.IntegerProperty(default=0)
  will_attend = db.IntegerProperty(default=0)
  flagged = db.IntegerProperty(default=0)

  # Blacklist is controlled by the moderators only, it is not a statistic.
  blacklisted = db.IntegerProperty(default=0)

  @classmethod
  def increment(cls, volunteer_opportunity_id, relative_attributes,
                absolute_attributes=None):
    """Helper to increment volunteer opportunity stats.

    Example:
      VolunteerOpportunityStats.increment(opp_id,
        { USER_INTEREST_LIKED: 1, USER_INTEREST_WILL_ATTEND: 1 })

    Args:
      volunteer_opportunity_id: ID of opportunity.
      relative_attributes: Dictionary of attr_name:value pairs to set as
          relative to current value.
      absolute_attributes: Dictionary of attr_name:value pairs to set as
          absolute values.
    Returns:
      Success boolean
    """
    entity = VolunteerOpportunityStats.get_or_insert(
        cls.DATASTORE_PREFIX + volunteer_opportunity_id)
    if not entity:
      return False

    (new_entity, unused_deltas) = \
        modelutils.set_entity_attributes(entity, absolute_attributes,
                                         relative_attributes)
                                         
    memcache.set(cls.MEMCACHE_PREFIX + volunteer_opportunity_id, new_entity,
                 time=cls.MEMCACHE_TIME)
    return True

  @classmethod
  def set_blacklisted(cls, volunteer_opportunity_id, value):
    """Helper to set volunteer opportunity value and update memcache."""
    # A wrapper for 'increment'--it's overkill, but manages memcache for us.
    return cls.increment(volunteer_opportunity_id, {}, {'blacklisted' : value})

  @classmethod
  def add_default_entities_to_memcache(cls, ids):
    """Add blank entities to memcache so get_by_ids quickly returns them."""
    entities = {}
    for key in ids:
      entities[key] = cls(key_name= cls.DATASTORE_PREFIX + key)
    memcache.add_multi(entities, time=cls.MEMCACHE_TIME,
                       key_prefix=cls.MEMCACHE_PREFIX)


class VolunteerOpportunity(db.Model):
  """Basic information about opportunities.

  Separate from VolunteerOpportunityStats because these entries need not be
  operated on transactionally since there's no counts.
  """
  # The __key__ is 'id:' + volunteer_opportunity_id
  DATASTORE_PREFIX = 'id:'
  MEMCACHE_PREFIX = 'VolunteerOpportunity:'
  MEMCACHE_TIME = 60000  # seconds

  # Information about the opportunity
  # URL to the Google Base entry
  base_url = db.StringProperty()
  # When we last update the Base URL.
  last_base_url_update = db.DateTimeProperty()
  # Incremented (possibly incorrectly to avoid transactions) when we try
  # to load the data from base but fail. Also the last date/time seen.
  base_url_failure_count = db.IntegerProperty(default=0)
  last_base_url_update_failure = db.DateTimeProperty()


# TODO(paul): added_to_calendar, added_to_facebook_profile, etc

USER_INTEREST_LIKED = 'liked'
USER_INTEREST_WILL_ATTEND = 'will_attend'
USER_INTEREST_FLAGGED = 'flagged'

USER_INTEREST_ATTRIBUTES = (
  USER_INTEREST_LIKED,
  USER_INTEREST_WILL_ATTEND,
  USER_INTEREST_FLAGGED,
)
