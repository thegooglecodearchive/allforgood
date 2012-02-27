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
main() for sheetchecker
"""

# view classes aren inherently not pylint-compatible
# pylint: disable-msg=C0103
# pylint: disable-msg=W0232
# pylint: disable-msg=E1101
# pylint: disable-msg=R0903

import logging
import re
import os
from urllib import unquote

from google.appengine.api import urlfetch
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template

import sheetchecker.parse_gspreadsheet as parse_gspreadsheet
import geocode

CHECK_SHEET_TEMPLATE = "checksheet.html"

def render_template(template_filename, template_values):
  """wrapper for template.render() which handles path."""
  path = os.path.join(os.path.dirname(__file__),
                      template_filename)
  rendered = template.render(path, template_values)
  return rendered

class Check(webapp.RequestHandler):
  """prefix query on sheetchecker."""
  def get(self):
    """HTTP get method."""
    sheeturl = self.request.get('url')
    template_values = {
      "sheeturl" : sheeturl,
      "sheetfeedurl" : "",
      "msgs" : None,
      "data" : None
      }
    match = re.search(r'key=([^& ]+)', sheeturl)
    if match:
      url = "http://spreadsheets.google.com/feeds/cells/"
      url += match.group(1).strip() + "/1/public/basic"
      fetch_result = urlfetch.fetch(url)
      if fetch_result.status_code != 200:
        self.response.out.write("<html><body>error fetching URL " +
                                url + "</body></html>")
        return
      contents = fetch_result.content
      logging.info("fetched %d bytes: %s..." % (len(contents), contents[:80]))
      data, msgs, addr_ar, urls_ar = parse_gspreadsheet.parse(contents)
      logging.info("%d msgs in %s" % (len(msgs), sheeturl))
      template_values["sheetfeedurl"] = url
      template_values["msgs"] = msgs
      template_values["data"] = data
      template_values["addresses"] = addr_ar
      template_values["urls"] = urls_ar
    elif sheeturl != "":
      self.response.out.write("<html><body>malformed sheet URL " +
                              " - missing &key=</body></html>")
      return
    self.response.out.write(template.render(CHECK_SHEET_TEMPLATE,
                                            template_values))
    
class ValidateAddress(webapp.RequestHandler):
  """validate address"""
  def get(self):
    """HTTP get method."""
    addr = unquote(self.request.get('address'))

    rsp = """
<html><body style="padding-top:1px;margin:0;font-size:10px;
font-weight:bold;text-align:center;background-color:%s;">%s
"""
    if geocode.geocode(addr) == "":
      rsp = rsp % ("#ff3333", "BAD")
    else:
      rsp = rsp % ("#33ff33", "OK")

    self.response.out.write(rsp);

   
class ValidateURL(webapp.RequestHandler):
  """validate address"""
  def get(self):
    """HTTP get method."""
    url = unquote(self.request.get('url'))

    if not url.startswith('http'):
      url = 'http://' + url

    if url == "":
      success = False
    else:
      try:
        fetch_result = urlfetch.fetch(url)
        if fetch_result.status_code >= 400:
          success = False
        else:
          success = True
      except:
        success = False

    rsp = """
<html><body style="padding-top:1px;margin:0;font-size:10px;
font-weight:bold;text-align:center;background-color:%s;">%s
"""
    if success:
      rsp = rsp % ("#33ff33", "OK")
    else:
      rsp = rsp % ("#ff3333", "BAD")

    self.response.out.write(rsp);


APP = webapp.WSGIApplication(
  [ ('/sheetchecker/check', Check),
    ('/sheetchecker/validate_address', ValidateAddress),
    ('/sheetchecker/validate_url', ValidateURL)
  ],
  debug=True)

def main():
  """main for standalone execution."""
  run_wsgi_app(APP)

if __name__ == "__main__":
  main()
