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

from datetime import datetime
import solr_search
import logging
import api

def query_time_boosts(args):
  logging.info("boosts.query_time_boosts enter")

  solr_query = ""
  fq = ""
  if args[api.PARAM_Q].find('category:IAMS') >= 0:
    solr_query = solr_search.rewrite_query('%s' %
        '(-PETA AND (dog OR cat OR pet) AND (shelter OR adoption OR foster))')
  elif args[api.PARAM_Q].find('category:education') >= 0:
    solr_query = solr_search.rewrite_query('(%s)' % 
        '((education OR tutoring)'
      + ' -feed_providername:girlscouts -prison -prisoner -inmate -disaster -emergency)')

  return solr_query, fq
