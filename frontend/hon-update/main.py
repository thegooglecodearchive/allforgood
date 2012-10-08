"""
"""

from google.appengine.dist import use_library
use_library('django', '1.2')

from datetime import datetime
import os
import sys
import locale
import hashlib
import urllib
import logging

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

import private_keys

class handleRequest(webapp.RequestHandler):
  """ handle request """

  def get(self):
    """ handle get request """
    hub(self, False)

  def post(self):
    """ handle post request """
    hub(self, True)


def redirector(app, url, is_post):

  code = 307 if is_post else 302
  if not is_post:
    # add the parameters 
    url += '?'
    
  logging.info(str(code) + ' redirect: ' + url)
  app.response.set_status(code, app.response.http_status_message(code))
  app.response.headers['Location'] = url


def hub(app, is_post):
  """ get results from datastore or API """

  for node in [private_keys.NODE1, private_keys.NODE2]:
    url = node + '/~footprint/'
    path = app.request.path.rstrip('/')
    if path == '/hon-update':
      redirector(app, url + 'hon-update.php', is_post)
    elif path == '/hon-delete':
      redirector(app, url + 'hon-delete.php', is_post)
    elif path == '/hon-add':
      redirector(app, url + 'hon-add.php', is_post)
    elif path == '/hon-log':
      redirector(app, url + 'hon-log.php', is_post)
    else:
      logging.warning('redirect? ' + path)

         
APP = webapp.WSGIApplication(
    [ (".*", handleRequest)
    ], debug=True)

def main():
  """ this program starts here """
  run_wsgi_app(APP)


if __name__ == '__main__':
  main()
