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
toss all the one-off boosts into one place (rather than a class file)
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
  elif args[api.PARAM_Q].find('category:MLKDay') >= 0:
      # eg, q=ballroom and category:MLKDay
      solr_query = args[api.PARAM_Q].replace('category:MLKDay', '').replace('( OR )', '').strip()
      solr_query += (' -feed_providername:meetup AND ('
                 + ' eventrangestart:[2011-01-08T00:00:00.000Z TO 2011-01-23T23:59:59.999Z]^20'
                 + ' OR title:(mlk and (\'day on not a day off\'))^20'
                 + ' OR title:mlk^10'
                 + ' OR title:mlktech^10'
                 + ' OR title:(\'ml king\')^10'
                 + ' OR title:(\'king day\')^10'
                 + ' OR title:(\'martin luther\')^10'
                 + ' OR abstract:(mlk and (\'day on not a day off\'))^20'
                 + ' OR abstract:(\'day on not a day off\')^10'
                 + ' OR abstract:mlk^10'
                 + ' OR abstract:mlktech^10'
                 + ' OR abstract:(\'ml king\')^5'
                 + ' OR abstract:(\'king day\')^5'
                 + ' OR abstract:(\'martin luther\')^5'
                 + ' OR (eventrangestart:[* TO 2011-01-08T00:00:00.000Z]'
                 + ' AND eventrangeend:[2011-01-23T00:00:00.000Z TO *])'
                 + ')')
  else:
     solr_query = "" 
  return solr_query