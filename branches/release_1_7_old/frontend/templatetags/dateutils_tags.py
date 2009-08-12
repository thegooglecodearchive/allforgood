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
Custom filters and tags for dates.
"""

from datetime import date
from django.utils import dateformat
from google.appengine.ext.webapp import template


def custom_date_format(value):
  """Converts a date to a string concatenating the month (in full text) with the
  day of the month (without leading zeros) and the year (4 digits) if it is not
  the current one."""
  if not value:
    return ''
  elif value.year < date.today().year:
    return 'Present'
  elif value.year == date.today().year:
    return dateformat.format(value, 'F j')
  else:
    return dateformat.format(value, 'F j, Y')  

# Prevents pylint from triggering on the 'register' name. Django expects this
# module to have a 'register' variable.
# pylint: disable-msg=C0103
register = template.create_template_register()
register.filter(custom_date_format)
