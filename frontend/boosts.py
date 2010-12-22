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
toss all the query-time boost code into one place (rather than a class file)
"""

from datetime import datetime
import solr_search
import logging
import api

def query_time_boosts(args):
  logging.info("boosts.query_time_boosts enter")
  if args[api.PARAM_Q].find('category:IAMS') >= 0:
      solr_query = solr_search.rewrite_query('%s' %
        '(-PETA AND (dog OR cat OR pet) AND (shelter OR adoption OR foster) AND category:Animals)')
  elif args[api.PARAM_CATEGORY] == "mlk":
      solr_query = solr_search.rewrite_query('(categories:MLK'
                 + ' OR eventrangestart:[2011-01-17T00:00:00.000Z TO 2011-01-17T23:59:59.999Z]^20'
                 + ' OR eventrangestart:[2011-01-17T00:00:00.000Z TO 2011-01-22T23:59:59.999Z]^5'
                 + ' OR title:(mlk and (\'day of service\'))^20'
                 + ' OR title:mlk^10'
                 + ' OR title:(\'ml king\')^10'
                 + ' OR title:(\'martin luther\')^10'
                 + ' OR abstract:(mlk and (\'day of service\'))^20'
                 + ' OR abstract:(\'day of service\')^10'
                 + ' OR abstract:mlk^10'
                 + ' OR abstract:(\'ml king\')^5'
                 + ' OR abstract:(\'martin luther\')^5'
                 + ' OR (blood AND (eventrangestart:[2011-01-17T00:00:00.000Z TO 2011-01-17T23:59:59.999Z] OR eventrangestart:[2011-01-17T00:00:00.000Z TO 2011-01-22T23:59:59.999Z])))')
  else:
     solr_query = "" 
  return solr_query