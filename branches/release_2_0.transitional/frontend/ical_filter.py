# Copyright 2010 Google Inc.
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
A utility library for parsing iCalendar recurrence specification and matching date ranges against them. 
Parameters supported: FREQ (DAILY, WEEKLY, MONTHLY), BYDAY, BYMONTHDAY.
"""

import datetime

WEEKDAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]

def parse_date(date_string):
  if date_string:
    return datetime.datetime.strptime(date_string, "%Y-%m-%d").date()
  else:
    None

def parse_ical(ical_string):
  try:
    return dict(p.split("=") for p in ical_string.split(";"))
  except ValueError:
    return dict()

def weekday_in_range(weekday, startdate, enddate):
  if (enddate - startdate).days >= 6:
    # All days of week are covered.
    return True
  start_wd = startdate.weekday()
  end_wd = enddate.weekday()
  if start_wd <= end_wd:
    return start_wd <= weekday <= end_wd
  else:
    return not end_wd < weekday < start_wd

def month_days(month, year):
  if month == 2:
    if year % 4:
      return 28
    elif year % 100:
      return 29
    elif year % 400:
      return 28
    else:
      return 29
  elif month in [4, 6, 9, 11]:
    return 30
  else:
    return 31

def monthday_in_range(day, startdate, enddate):
  months_diff = enddate.month - startdate.month + 12 * (enddate.year - startdate.year)
  if months_diff >= 3:
    # There are two full consecutive months covered, one must have 31 days.
    return True
  if months_diff == 0:
    return startdate.day <= day <= enddate.day

  # months_diff in [1,2]
  if startdate.day <= day <= month_days(startdate.month, startdate.year):
    return True
  if day <= enddate.day:
    return True

  if months_diff == 2:
    middle_month = (start_month % 12) + 1
    middle_month_year = startdate.year + 1 if middle_month == 1 else startdate.year
    if day <= month_days(middle_month, middle_month_year):
      return True

  return False

def match(ical_recurrence, query_startdate, query_enddate):
  startdate = parse_date(query_startdate) or datetime.date.min
  enddate = parse_date(query_enddate) or datetime.date.max

  ical = parse_ical(ical_recurrence)

  if "FREQ" not in ical:
    # No FREQ, bailing out.
    return True

  freq = ical["FREQ"]
  if freq == "WEEKLY":
    if "BYDAY" not in ical:
      # No BYDAY, bailing out.
      return True
    bydays = ical["BYDAY"].split(",")
    if bydays == []:
      # No weekdays specified, bailing out.
      return True
    for byday in bydays:
      if byday not in WEEKDAYS:
        continue
      weekday = WEEKDAYS.index(byday)
      if weekday_in_range(weekday, startdate, enddate):
        return True
    return False
  elif freq == "MONTHLY":
    if "BYMONTHDAY" not in ical:
      # No BYMONTHDAY, bailing out.
      return True
    days = [int(day) for day in ical["BYMONTHDAY"].split(",")]
    if days == []:
      # No monthdays specified, bailing out.
      return True
    for day in days:
      if day < 1 or day > 31:
        continue
      if monthday_in_range(day, startdate, enddate):
        return True
    return False
  else:
    # The iCal string is invalid/unsupported, bailing out.
    # Possibly a daily schedule, in which case we also return True.
    return True
