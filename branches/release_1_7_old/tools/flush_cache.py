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
#

"""Script to flush the cache on an allforgood.org site

Follows the general procedure outlined at 
http://code.google.com/apis/accounts/docs/AuthForInstalledApps.html
for accessing the google ClientLogin interface, receiving an 
authorization token and using that to access an authenticaiton-required
page on our domain.
"""

import sys
import urllib
import urllib2
import cookielib
import getpass

def verify_flush(serv_resp_body):
  """Check the body of a response to see if memcached was flushed"""
  
  return "memcached flushed" in serv_resp_body

def flush_footprint_cache(host, app_name, 
                          users_email_address, users_password):
  """Flush the cache on the specified server"""

  flush_uri = 'http://%s/admin?action=flush_memcache' % host

  # we use a cookie to authenticate with Google App Engine
  #  by registering a cookie handler here, this will automatically store the
  #  cookie returned when we use urllib2 to open 
  # http://ourapp.appspot.com/_ah/login
  cookiejar = cookielib.MozillaCookieJar('cache-cookies-mozilla')
  
  opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookiejar))
  urllib2.install_opener(opener)

  # get an AuthToken from Google accounts
  auth_uri = 'https://www.google.com/accounts/ClientLogin'
  authreq_data = urllib.urlencode({ "Email": users_email_address,
                                   "Passwd": users_password,
                                   "service": "ah",
                                   "source": app_name,
                                   "accountType": "HOSTED_OR_GOOGLE" })
  auth_req = urllib2.Request(auth_uri, data=authreq_data)
  auth_resp = urllib2.urlopen(auth_req)
  auth_resp_body = auth_resp.read()
  # auth response includes several fields - we're interested in
  #  the bit after Auth=
  auth_resp_dict = dict(x.split("=")
                       for x in auth_resp_body.split("\n") if x)
  authtoken = auth_resp_dict["Auth"]

  #
  # get a cookie
  #
  #  the call to request a cookie will also automatically redirect us to 
  #   the page that we want to go to
  #  the cookie jar will automatically provide the cookie when we reach the
  #   redirected location

  # this is where I actually want to go to
  print 'Received auth token, calling login and flush URL...'
  serv_uri = flush_uri

  serv_args = {}
  serv_args['continue'] = serv_uri
  serv_args['auth'] = authtoken
  
  login_uri = "http://%s/_ah/login?%s" % (host, urllib.urlencode(serv_args))

  serv_req = urllib2.Request(login_uri)
  serv_resp = urllib2.urlopen(serv_req)
  serv_resp_body = serv_resp.read()

  # serv_resp_body should contain the contents of the
  #  target_authenticated_google_app_engine_uri page - as we will have been
  #  redirected to that page automatically
  
  return serv_resp_body

def main():
  """Main routine"""
  
  if len(sys.argv) < 4:
    print 'USAGE: flush_cache.py <host> <app_name> <email> [password]'
    sys.exit(-1)
  
  host = sys.argv[1]
  app_name = sys.argv[2]
  email = sys.argv[3]
  
  if len(sys.argv) < 5:
    passwd = getpass.getpass("Password for " + email + ": ")
  else:
    passwd = sys.argv[4]
  
  response = flush_footprint_cache(host, app_name, email, passwd)
  if verify_flush(response):
    print 'Cache flushed!'
  else:
    print '*** Error flushing cache. Response of last URL request:'
    print response

if __name__ == '__main__':
  main()
