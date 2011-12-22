"""
track API calls in Google Analytics
http://code.google.com/mobile/analytics/docs/web/
http://code.google.com/appengine/docs/python/urlfetch/asynchronousrequests.html
http://www.google.com/support/forum/p/Google+Analytics/thread?tid=190fadf79aeb19a7&hl=en
http://www.google.com/support/forum/p/Google%20Analytics/thread?tid=1d2ce688a2e0b0df&hl=en
"""

import urllib
import random
import logging

from google.appengine.api import urlfetch

import private_keys

def handle_result(rpc):
  
  try:
    result = rpc.get_result()
    logging.info('track call made')
    if result.status_code != 200:
      logging.warning('track call returned ' + str(result.status_code))
  except:
    logging.warning('track call failed')


def create_callback(rpc):
  return lambda: handle_result(rpc)


def track(category = "", action = "", label = ""):

  if random.random() < 0.5:
    node = private_keys.NODE1
  else:
    node = private_keys.NODE2

  url = ("%s/~footprint/track.php?category=%s&action=%s&label=%s&nocache=%s" % 
          (node, urllib.quote_plus(category.replace(' ', '_'), 
                 urllib.quote_plus(action.replace(' ', '_'), 
                 urllib.quote_plus(label.replace(' ', '_'), str(random.random())
          )
        )

  # async w/ callback
  rpc = urlfetch.create_rpc(1)
  rpc.callback = create_callback(rpc)
  logging.info('track call %s' % url)
  urlfetch.make_fetch_call(rpc, url)


