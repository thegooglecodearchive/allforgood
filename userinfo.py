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

"""User Info module (userinfo).

This file contains the base class for the userinfo classes.
It also contains (at least for now) subclasses for different login types."""

__author__ = 'matthew.blain@google.com'

import logging
import os

from django.utils import simplejson
from versioned_memcache import memcache
from google.appengine.api import urlfetch
from StringIO import StringIO
from facebook import Facebook

import deploy
import models
import utils


class Error(Exception): pass
class NotLoggedInError(Error): pass
class ThirdPartyError(Error): pass

USERINFO_CACHE_TIME = 120  # seconds

# Keys specific to Footprint
FRIENDCONNECT_KEY = '02962301966004179520'

def get_cookie(cookie_name):
  if 'HTTP_COOKIE' in os.environ:
    cookies = os.environ['HTTP_COOKIE']
    cookies = cookies.split('; ')
    for cookie in cookies:
      cookie = cookie.split('=')
      if cookie[0] == cookie_name:
        return cookie[1]

def get_user(request):
  for cls in (TestUser, FriendConnectUser, FacebookUser):
    cookie = cls.get_cookie()
    if cookie:
      key = 'cookie:' + cookie
      user = memcache.get(key)
      if not user:
        try:
          user = cls(request)
          memcache.set(key, user, time = USERINFO_CACHE_TIME)
        except:
          # This hides all errors from the Facebook client library
          # TODO(doll): Hand back an error message to the user
          logging.exception("Facebook or Friend Connect client exception.")
          return None
      return user

def get_usig(user):
  """Get a signature for the current user suitable for an XSRF token."""
  if user and user.get_cookie():
    return utils.signature(user.get_cookie())


class User(object):
  """The User info for a user related to a currently logged in session.."""

  def __init__(self, account_type, user_id, display_name, thumbnail_url):
    self.account_type = account_type
    self.user_id = user_id
    self.display_name = display_name
    self.thumbnail_url = thumbnail_url
    self.user_info = None
    self.friends = None
    self.total_friends = None

  @staticmethod
  def get_current_user(self):
    raise NotImplementedError

  def get_user_info(self):
    if not self.user_info:
      self.user_info = models.UserInfo.get_or_insert_user(self.account_type,
                                                          self.user_id)
    return self.user_info

  def load_friends(self):
    key_suffix = self.account_type + ":" + self.user_id
    key = 'friends:' + key_suffix
    total_key = 'total_friends:' + key_suffix
    self.friends = memcache.get(key)
    self.total_friends = memcache.get(total_key)
    if not self.friends:
      self.friends = self.get_friends_by_url();
      memcache.set(key, self.friends, time = USERINFO_CACHE_TIME)
      memcache.set(total_key, self.total_friends, time = USERINFO_CACHE_TIME)
    return self.friends

  def get_friends_by_url(self):
    raise NotImplementedError

  @classmethod
  def is_logged_in(cls):
    cookie = cls.get_cookie()
    return not not cookie


class FriendConnectUser(User):
  """A friendconnect user."""

  BASE_URL = 'http://www.google.com/friendconnect/api/people/'

  USER_INFO_URL = BASE_URL + '@viewer/@self?fcauth=%s'
  FRIEND_URL = BASE_URL + '@viewer/@friends?fcauth=%s'

  def __init__(self, request):
    """Creates a friendconnect user from the current env, or raises error."""
    self.fc_user_info = self.get_fc_user_info()
    super(FriendConnectUser, self).__init__(
        models.UserInfo.FRIENDCONNECT,
        self.fc_user_info['entry']['id'],
        self.fc_user_info['entry']['displayName'],
        self.fc_user_info['entry']['thumbnailUrl'])

  def get_friends_by_url(self):
    friend_cookie = self.get_cookie()
    if not friend_cookie:
      raise NotLoggedInError()

    self.friends = []

    url = self.FRIEND_URL % friend_cookie
    result = urlfetch.fetch(url)
    if result.status_code == 200:
      friend_info = simplejson.load(StringIO(result.content))
      self.total_friends = friend_info['totalResults']

      for friend_object in friend_info['entry']:
        friend = User(
            models.UserInfo.FRIENDCONNECT,
            friend_object['id'],
            friend_object['displayName'],
            friend_object['thumbnailUrl'])
        self.friends.append(friend)

    return self.friends

  @classmethod
  def get_cookie(cls):
    return get_cookie('fcauth' + FRIENDCONNECT_KEY)

  @classmethod
  def get_fc_user_info(cls):
    friend_cookie = cls.get_cookie()
    if not friend_cookie:
      raise NotLoggedInError()
      return

    url = cls.USER_INFO_URL % friend_cookie
    result = urlfetch.fetch(url)

    if result.status_code == 200:
      user_info = simplejson.load(StringIO(result.content))
      return user_info
    else:
      raise ThirdPartyError()


class FacebookUser(User):
  def __init__(self, request):
    self.facebook = Facebook(deploy.get_facebook_key(),
                             deploy.get_facebook_secret())
    if not self.facebook.check_connect_session(request):
      raise NotLoggedInError()

    info = self.facebook.users.getInfo([self.facebook.uid],
        ['name', 'pic_square_with_logo'])[0]

    super(FacebookUser, self).__init__(
        models.UserInfo.FACEBOOK,
        self.facebook.uid,
        info['name'],
        info['pic_square_with_logo'])

  def get_friends_by_url(self):
    if not self.facebook:
      raise NotLoggedInError()

    self.friends = []

    friend_ids = self.facebook.friends.getAppUsers()
    if not friend_ids or len(friend_ids) == 0:
      friend_ids = []  # Force return type to be a list, not a dict or None.
    self.total_friends = len(friend_ids)

    # TODO: handle >20 friends.
    friend_objects = self.facebook.users.getInfo([friend_ids[0:20]],
        ['name', 'pic_square_with_logo'])
    for friend_object in friend_objects:
      friend = User(
          models.UserInfo.FACEBOOK,
          `friend_object['uid']`,
          friend_object['name'],
          friend_object['pic_square_with_logo'])
      self.friends.append(friend)

    return self.friends

  @classmethod
  def get_cookie(cls):
    return get_cookie(deploy.get_facebook_key())


class TestUser(User):
  """A really simple user example."""

  def __init__(self, request):
    """Creates a user, or raises error."""
    cookie = self.get_cookie()
    if not (cookie):
      raise NotLoggedInError()
    super(TestUser, self).__init__(
        models.UserInfo.TEST,
        cookie,
        cookie,
        'images/Event-Selected-Star.png')

  @classmethod
  def get_cookie(cls):
    return get_cookie('footprinttest')

  def get_friends_by_url(self):
     # TODO: Something clever for testing--like all TestUser?
    return []
