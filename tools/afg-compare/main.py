#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
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

import os
import re
import urllib
import logging
import time

import wsgiref.handlers

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.api import urlfetch

from xml.dom import minidom

def getTagText(item, tag):
  node = item.getElementsByTagName(tag)[0]
  try:
    c = node.firstChild
    if c.nodeType == c.TEXT_NODE:
      return c.data
    else:
      return 'No value for ' + c.tagName
  except:
    return ''
    
def getItemInfo(afgitem):
  info = {}
  info['title'] = getTagText(afgitem, 'title')
  info['description'] = getTagText(afgitem, 'description')
  info['link'] = getTagText(afgitem, 'link')
  info['guid'] = getTagText(afgitem, 'guid')
  info['startdate'] = getTagText(afgitem, 'fp:startDate')
  info['enddate'] = getTagText(afgitem, 'fp:endDate')
  info['location'] = getTagText(afgitem, 'fp:location_name')
  return info

def getAFGAPI(base_url, query, location):
  """Call the AFG API and return the result"""

  url = base_url.rstrip('/')
  url += '/api/volopps?key=goody2shoes&output=rss'
  url += '&vol_loc=%s' % urllib.quote_plus(location)
  url += '&q=%s' % urllib.quote_plus(query)

  start_time = time.time()
  logging.info("fetching "+url)
  result = urlfetch.fetch(url)
  end_time = time.time()

  # Return latency in msec
  latency = (end_time - start_time) * 1000.0

  return (url, result, latency)


class VMCompareHandler(webapp.RequestHandler):
  """Run the compare against VM"""
  def get(self):

    left_base_url = self.request.get('left')
    query = self.request.get('query')
    loc = self.request.get('loc')
    
    template_values = { 
      'left_base_url': left_base_url, 
      'left_url': '',
      'right_url': 'http://www.volunteermatch.org/',
      'location': loc,
      'results': False,
      'query': query,
    }

    if left_base_url:
      (left_query_url, left_result, left_latency) = getAFGAPI(left_base_url, query, loc)
      template_values['left_url'] = left_query_url
      template_values['left_latency'] = left_latency
      left_rss = left_result.content
      dom1 = minidom.parseString(left_rss)
      left_results = [getItemInfo(i) for i in dom1.getElementsByTagName('item')]
      dom1.unlink()

      # optional VM category
      match = re.search('category:([a-zA-Z0-9._-]+)', query)
      vmcat = ""
      if match:
        afgcat = match.group(1).lower()
        if afgcat.find('nature') >= 0:
          vmcat = '&categories=13'   # Environment
        elif afgcat.find('education') >= 0:
          vmcat = '&categories=15'   # Education & Literacy
        elif afgcat.find('animals') >= 0:
          vmcat = '&categories=30'   # Animals
        elif afgcat.find('health') >= 0:
          vmcat = '&categories=11'   # Health & Medicine
        elif afgcat.find('seniors') >= 0:
          vmcat = '&categories=12'   # Seniors
        elif afgcat.find('technology') >= 0:
          vmcat = '&categories=37'   # Computers & Technology
        elif afgcat.find('hunger') >= 0:
          vmcat = '&categories=39'   # Hunger
        elif afgcat.find('tutoring') >= 0:
          # no VM equivalent, just search on tutoring
          query += " tutoring"
        else:
          logging.error("unknown category: "+afgcat)
        query = re.sub('category:([a-zA-Z0-9._-]+)', '', query)

      # Figure out VM URL
      vm_url = 'http://www.volunteermatch.org/search/index.jsp?l=%s&k=%s' % (
        urllib.quote_plus(loc), urllib.quote_plus(query))
      vm_url += vmcat
        
      template_values['right_url'] = vm_url
      template_values['results'] = True
      template_values['left_results'] = left_results
    else:
      # Add default value for left_base_url
      template_values['left_base_url'] = 'http://www.allforgood.org/'

    path = os.path.join(os.path.dirname(__file__), 'vm_compare.html')
    self.response.out.write(template.render(path, template_values))


class CompareHandler(webapp.RequestHandler):
  """Run the compare"""
  def get(self):

    left_base_url = self.request.get('left')
    right_base_url = self.request.get('right')
    query = self.request.get('query')
    loc = self.request.get('loc')

    template_values = { 
      'left_base_url': left_base_url, 
      'right_base_url': right_base_url, 
      'left_url': '',
      'right_url': '',
      'query': query,
      'location': loc,
      'results': 'yes'
    }

    (left_query_url, left_result, left_latency) = getAFGAPI(left_base_url, query, loc)
    template_values['left_url'] = left_query_url
    template_values['left_latency'] = left_latency
    left_rss = left_result.content
    dom1 = minidom.parseString(left_rss)
    left_results = [getItemInfo(i) for i in dom1.getElementsByTagName('item')]
    dom1.unlink()
    
    template_values['results'] = left_results

    (right_query_url, right_result, right_latency) = getAFGAPI(right_base_url, query, loc)
    template_values['right_url'] = right_query_url
    template_values['right_latency'] = right_latency
    dom1 = minidom.parseString(right_result.content)
    right_results = [getItemInfo(i) for i in dom1.getElementsByTagName('item')]
    dom1.unlink()

    all_results = zip(left_results, right_results)
    template_values['results'] = all_results

    path = os.path.join(os.path.dirname(__file__), 'compare.html')
    self.response.out.write(template.render(path, template_values))

class MainHandler(webapp.RequestHandler):
  def get(self):
    template_values = {
      'left_base_url': 'http://www.allforgood.org',
      'right_base_url': 'http://www.footprint2009qa.appspot.com',
    }
    path = os.path.join(os.path.dirname(__file__), 'compare.html')
    self.response.out.write(template.render(path, template_values))


def main():
  application = webapp.WSGIApplication(
    [ ('/', MainHandler),
      ('/compare', CompareHandler),
      ('/vmcompare', VMCompareHandler),
    ],
    debug=True)
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()
