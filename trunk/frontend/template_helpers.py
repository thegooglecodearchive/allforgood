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
Functions for working with Django templates.
"""
import re
import os
import urllib
import logging
from google.appengine.ext.webapp import template
from datetime import datetime

import userinfo
import deploy

TEMPLATE_DIR = 'templates/'

def get_default_template_values(request, current_page):
  """for debugging login issues"""
  no_login = (request.get('no_login') == "1")

  version = request.get('dbgversion')
  # don't allow junk
  if not version or not re.search(r'^[0-9a-z._-]+$', version):
    version = os.getenv('CURRENT_VERSION_ID')

  template_values = {
    'user' : userinfo.get_user(request),
    'current_page' : current_page,
    'host' : urllib.quote(request.host_url),
    'path' : request.path,
    'version' : version,
    'no_login' : no_login,
    'optimize_page' : optimize_page_speed(request),
    'view_url': request.url,
    }
  load_userinfo_into_dict(template_values['user'], template_values)
  return template_values

def optimize_page_speed(request):
  """OK to optimize the page: minimize CSS, minimize JS, Sprites, etc."""
  # page_optim=1 forces optimization
  page_optim = request.get('page_optim')
  if page_optim == "1":
    return True
  # page_debug=1 forces no optimization
  page_debug = request.get('page_debug')
  if page_debug == "1":
    return False
  # optimize in production and on appspot
  if (request.host_url.find("appspot.com") >= 0 or
      request.host_url.find("allforgood.org") >= 0):
    return True
  return False

def load_userinfo_into_dict(user, userdict):
  """populate the given dict with user info."""
  if user:
    userdict["user"] = user
    userdict["user_days_since_joined"] = (datetime.now() -
                                          user.get_user_info().first_visit).days
  else:
    userdict["user"] = None
    userdict["user_days_since_joined"] = None

def render_template(template_filename, template_values):
  """wrapper for template.render() which handles path."""
  path = os.path.join(os.path.dirname(__file__),
                      TEMPLATE_DIR + template_filename)
  deploy.load_standard_template_values(template_values)
  rendered = template.render(path, template_values)
  return rendered
