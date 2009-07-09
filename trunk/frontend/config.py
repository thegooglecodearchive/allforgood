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

"""Configuration class.

This class provides a dictionary of run-time configuration options for the
application.
You can edit the values in the datastore editor of the admin console or other
datastore editing tools.

The values are cached both in memcache (which can be flushed) and locally
in the running Python instance, which has an indeterminite but typically short
life time.

To use the class:
import config
configvalue = config.config.get_value('valuename')
"""

from google.appengine.api import memcache
from google.appengine.ext import db


class Config(db.Model):
  """Configuration parameters.
  
  The key name is used as the name of the parameter.
  """
  description = db.StringProperty()
  value = db.StringProperty(required=True)

  MEMCACHE_ENTRY = 'Config'

  # Warning: do not add private/secret configuration values used in production
  # to these default values. The default values are intended for development.
  # Production values must be stored in the datastore.
  DEFAULT_VALUES = {}

  local_config_cache = None

  @classmethod
  def get_value(cls, name):
    """Retrieves the value of a configuration parameter.
    
    Args:
      name: the name of the parameter whose value we are looking for.

    Returns:
      The value of the parameter or None if the parameter is unknown.
    """
    if cls.local_config_cache is None:
      # The local cache is empty, retrieve its content from memcache.
      cache = memcache.get(cls.MEMCACHE_ENTRY)
      if cache is None:
        # Nothing in memcache either, recreate the cache from the datastore.
        cache = dict(cls.DEFAULT_VALUES)
        for parameter in Config.all():
          cache[parameter.key().name()] = parameter.value
        # Save the full cache in memcache with 1h expiration time.
        memcache.add(cls.MEMCACHE_ENTRY, cache, 60*60)
      cls.local_config_cache = cache
    # Retrieve the value from the cache.
    return cls.local_config_cache.get(name)
