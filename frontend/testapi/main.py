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
main() for API testing framework
"""

# view classes aren inherently not pylint-compatible
# pylint: disable-msg=C0103
# pylint: disable-msg=W0232
# pylint: disable-msg=E1101
# pylint: disable-msg=R0903

import re
import os

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

import utils
import testapi.helpers

class DumpSampleData(webapp.RequestHandler):
  """print the contents of the static XML file."""
  def get(self):
    """HTTP get method."""
    path = os.path.join(os.path.dirname(__file__),
                        testapi.helpers.CURRENT_STATIC_XML)
    xmlfh = open(path, 'r')
    self.response.headers['Content-Type'] = 'text/xml'
    self.response.out.write(xmlfh.read())

class RunTests(webapp.RequestHandler):
  """main for running all tests."""
  def get(self):
    """HTTP get method."""
    ok_pattern = re.compile('[a-z0-9_,:/-]*$')
    try:
      testType = utils.get_verified_arg(ok_pattern, self.request,
                                        'test_type') or 'all'
      responseTypes = (utils.get_verified_arg(ok_pattern, self.request,
                                              'response_types') or
                       testapi.helpers.DEFAULT_RESPONSE_TYPES)
      remoteUrl = utils.get_verified_arg(ok_pattern, self.request, 'url')
      specialOutput = utils.get_verified_arg(ok_pattern, self.request,
                                             'output')
      # cache=0: don't read from cache, else read from cache.
      read_from_cache = not (self.request.get('cache') == '0')
    except utils.InvalidValue:
      self.error(400)
      return

    if specialOutput == 'test_types':
      self.response.out.write(testapi.helpers.ALL_TEST_TYPES)
      return

    errors = ''
    if not remoteUrl:
      errors = 'No remote url given in request, using default url'
      apiUrl = testapi.helpers.DEFAULT_TEST_URL
    else:
      apiUrl = remoteUrl

    outstr = ""
    outstr += '<style>'
    outstr += 'p {font-family: Arial, sans-serif; font-size: 10pt; margin: 0;}'
    outstr += 'p.error {color: #880000;}'
    outstr += '.test {font-size: 12pt; font-weight: bold; margin-top: 12px;}'
    outstr += '.uri {font-size: 10pt; font-weight: normal; color: gray;'
    outstr += '      margin-left: 0px;}'
    outstr += '.result {font-size: 11pt; font-weight: normal; '
    outstr += '      margin-left: 8px; margin-bottom: 4px;}'
    outstr += '.fail {color: #880000;}'
    outstr += '.success {color: #008800;}'
    outstr += '.amplification {color: gray; margin-left: 16px;}'
    outstr += '</style>'
    if read_from_cache:
      outstr += '<h1>Reading test: ' + testType + ' from the datastore</h1>'
    else:
      outstr += '<h1>Running test: ' + testType + '</h1>'
    outstr += '<p class="error">' + errors + '</p>'
    outstr += '<p>Response types: ' + responseTypes + '</p>'
    outstr += '<p>API url: ' + apiUrl + '</p>'
    self.response.out.write(outstr)

    final_status = 200
    responseTypes = responseTypes.split(',')
    for responseType in responseTypes:
      api_testing = testapi.helpers.ApiTesting(self)
      api_testing.run_tests(testType, apiUrl, responseType, read_from_cache)
      if api_testing.num_failures > 0 and final_status != 500:
        final_status = 500

    self.response.set_status(final_status)

APP = webapp.WSGIApplication(
  [('/testapi/run', RunTests),
   ('/testapi/sampleData.xml', DumpSampleData)],
  debug=True)

def main():
  """main for standalone execution."""
  run_wsgi_app(APP)

if __name__ == "__main__":
  main()
