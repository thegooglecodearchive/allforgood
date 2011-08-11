# Copyright 2009 Google Inc.  #
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
toss all the one-off boosts into one place (rather than a class file)
"""

DEFAULT_BOOSTS = [
  # boosting vetted categories
  ' categories:vetted^15',

  # big penalty for events starting in the far future
  ' eventrangestart:[* TO NOW+6MONTHS]^15',

  # big boost for events starting in the near future
  ' eventrangestart:[NOW TO NOW+1MONTHS]^10',

  # slight penalty for events started recently
  ' eventrangestart:[NOW TO *]^5',

  # modest penalty for events started long ago
  ' eventrangestart:[NOW-6MONTHS TO *]^7',

  # modest penalty for events ending in the far future
  ' eventrangeend:[* TO NOW+6MONTHS]^7',

  # big boost for events ending in the near future
  ' eventrangeend:[NOW TO NOW+1MONTHS]^10',

  # slight penalty for girl scout events
  ' (*:* -feed_providername:girlscouts)^200',

  # boost short events
  ' eventduration:[0 TO 10]^10',
]

CATEGORY_QUERIES = {
  'category:september11' : '(september11 OR (eventrangestart:[0001-01-01T00:00:00Z TO 2011-09-11T23:59:59Z]) AND (eventrangeend:[2011-09-11T00:00:00Z TO *]))',

  'category:IAMS' : '(-PETA AND (dog OR cat OR pet) AND (shelter OR adoption OR foster))',

  'category:education' : '((education OR tutoring) -feed_providername:girlscouts -prison -prisoner -inmate -disaster -emergency)',
}

CATEGORY_BOOSTS = {
  'category:education' : ' title:(school OR children OR student OR classroom)^100',
}

API_KEY_QUERIES = {'americanexpress' : '(feed_providername:handsonnetwork1800 OR feed_providername:handsonnetworkconnect) AND (911day OR (eventrangestart:[0001-01-01T00:00:00Z TO 2011-10-16T00:00:00Z] AND eventrangeend:[2011-08-11T00:00:00Z TO *]))',
}

API_KEY_BOOSTS = {
  'liveunited' : ' feed_providername:unitedway^2000 title:tutor^1000',

  'americanexpress' : ' title:911day^1000 description:911day^100',
}

FILTER_QUERIES = []
