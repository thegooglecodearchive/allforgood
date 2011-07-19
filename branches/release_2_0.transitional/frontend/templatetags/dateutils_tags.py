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
import datetime
from datetime import date
from django.utils import dateformat
from google.appengine.ext.webapp import template
from datetime import timedelta


# If opt_past_dates is set then past dates are not returned as "Present".
def custom_date_format(value, opt_past_dates = False):
  """Converts a date to a string concatenating the month (in full text) with the
  day of the month (without leading zeros) and the year (4 digits) if it is not
  the current one."""
  if not value:
    return ''
  elif value.year < date.today().year and not opt_past_dates:
    return 'Present'
  elif value.year == date.today().year:
    return dateformat.format(value, 'F j, Y')
  else:
    return dateformat.format(value, 'F j, Y')  

def custom_date_range_format(result):
  """Returns a formatted string with the date range of the SearchResult.
  If it is openEnded then "Ongoing" or "Starting ..." is returned.
  Otherwise, a date range or single date is returned.
  Since some existing ongoing data have an enddate in 1971, these are also
  printed as Ongoing"""
  
  threedays = timedelta(days=3)
  today_minus_three = datetime.datetime.today() - threedays
  
  if result.openEnded:
    if result.startdate.year <= date.today().year:
      return "Ongoing"
    else:
      return "Starting " + custom_date_format(result.startdate, True)
  else:
    if result.startdate.year > result.enddate.year:
      if result.startdate.year < date.today().year:
        return "Ongoing"
      else:
        return "Starting " + custom_date_format(result.startdate, True)
    if result.startdate < today_minus_three and result.enddate < today_minus_three:
        return "Ongoing"
    startdate = custom_date_format(result.startdate)
    enddate = custom_date_format(result.enddate)
    if startdate == enddate:
      return startdate
    else:
      return startdate + " - " + enddate

# Prevents pylint from triggering on the 'register' name. Django expects this
# module to have a 'register' variable.
# pylint: disable-msg=C0103
register = template.create_template_register()
register.filter(custom_date_format)
register.filter(custom_date_range_format)
