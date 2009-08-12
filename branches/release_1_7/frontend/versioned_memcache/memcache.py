#!/usr/bin/env python
#
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
#

"""Memcache wrapper that transparently adds app version

This wraps google.appengine.api.memcache, adding a namespace
parameter to all calls that is based on the app version 
environment variable (os.environ["CURRENT_VERSION_ID"]). This
means new versions of the app will not access cached entries
from an old version, so no cache flushing is required when
changing app versions.
"""

# Pylint doesn't like the names memcache uses -- disable those warnings
# pylint: disable-msg=W0622
# pylint: disable-msg=C0103

import os

from google.appengine.api import memcache

# The method called below sets the namespace used by any memcache 
# call whose namespace parameter is None (the default).
memcache.namespace_manager.set_request_namespace(
    os.environ["CURRENT_VERSION_ID"])

# Pass-throughs to memcache. By defining these here we give ourselves
# the flexibility to fix things if the above not-really-documented
# API changes or goes away.

set = memcache.set
set_multi = memcache.set_multi
get = memcache.get
get_multi = memcache.get_multi
delete = memcache.delete
delete_multi = memcache.delete_multi
add = memcache.add
add_multi = memcache.add_multi
replace = memcache.replace
replace_multi = memcache.replace_multi
incr = memcache.incr
decr = memcache.decr
flush_all = memcache.flush_all
get_stats = memcache.get_stats
Client = memcache.Client

