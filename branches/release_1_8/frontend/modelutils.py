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

"""Datastore helper methods."""

import datetime
import logging

from versioned_memcache import memcache
from google.appengine.ext import db

def set_entity_attributes(entity, absolute_attributes, relative_attributes):
  """Set entity attributes, using absolute or relative values.

  Args:
    model_class: model class
    key: Entity key.
    absolute_attributes: Dictionary of attr_name:value pairs to set.
    relative_attributes: Dictionary of attr_name:value pairs to set as
        relative to current value.  If some attr_name appears in both
        the absolute and relative dictionaries, the absolute is set first.

  Returns:
    On error: (None, None)
    On success: (entity, deltas)
      entity: The entity after applying the changes
      deltas: Dict of attr_name:delta_values, where each delta shows how
          the change in value in the respective attribute.
  """
  if not absolute_attributes:
    absolute_attributes = {}
  if not relative_attributes:
    relative_attributes = {}

  def txn(entity):
    # Passed 'entity' as function parameter because of python scope rules.

    entity = entity.get(entity.key())

    # Initialize the deltas list with starting values.  Also, set any undefined
    # attribute to zero.
    deltas = {}

    combined_attributes = (set([x for x in absolute_attributes.iterkeys()]) |
                           set([x for x in relative_attributes.iterkeys()]))
    for attr in combined_attributes:
      if not getattr(entity, attr):
        setattr(entity, attr, 0)  # Ensure all attributes are defined.
        deltas[attr] = 0
      else:
        deltas[attr] = getattr(entity, attr)

    # Set absolute values first.
    for attr in absolute_attributes.iterkeys():
      setattr(entity, attr, absolute_attributes[attr])

    # Set relative values.
    for attr in relative_attributes.iterkeys():
      # Here, we know getattr() is defined, since we initialized all undefined
      # attributes at the top of this function.
      setattr(entity, attr, getattr(entity, attr) + relative_attributes[attr])

    # Compute the final delta value for each attribute.
    for attr in combined_attributes:
      deltas[attr] = getattr(entity, attr) - deltas[attr]

    entity.put()
    return (entity, deltas)

  try:
    return_value = db.run_in_transaction(txn, entity)
    return return_value
  except Exception:
    logging.exception('set_entity_attributes failed for key %s' %
                      entity.key().id_or_name())
    return (None, None)


def get_by_ids(cls, ids):
  """Gets multiple entities for IDs, trying memcache then datastore.

  Args:
    cls: Model class
    ids: list of ids.
  Returns:
    Dictionary of results, id:model.
  """
  results = memcache.get_multi(ids, cls.MEMCACHE_PREFIX + ':')

  datastore_prefix = cls.DATASTORE_PREFIX
  missing_ids = []
  for id in ids:
    if not id in results:
      missing_ids.append(datastore_prefix + id)

  datastore_results = cls.get_by_key_name(missing_ids)
  for result in datastore_results:
    if result:
      result_id = result.key().name()[len(datastore_prefix):]
      results[result_id] = result

  return results
