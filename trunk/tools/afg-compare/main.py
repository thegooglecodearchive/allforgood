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
import urllib

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
  return info

def getAFGAPI(base_url, query, location):
  """Call the AFG API and return the result"""

  url = base_url.rstrip('/')
  url += '/api/volopps?key=goody2shoes&output=rss'
  url += '&vol_loc=%s' % urllib.quote_plus(location)
  url += '&q=%s' % urllib.quote_plus(query)

  result = urlfetch.fetch(url)
  return (url, result)

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

    (left_query_url, left_result) = getAFGAPI(left_base_url, query, loc)
    template_values['left_url'] = left_query_url
    left_rss = left_result.content
    dom1 = minidom.parseString(left_rss)
    left_results = [getItemInfo(i) for i in dom1.getElementsByTagName('item')]
    dom1.unlink()
    
    template_values['results'] = left_results

    (right_query_url, right_result) = getAFGAPI(right_base_url, query, loc)
    template_values['right_url'] = right_query_url
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
    ],
    debug=True)
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()
