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
appengine main() for when the site is down.
"""
# note: view classes aren inherently not pylint-compatible
# pylint: disable-msg=C0103
# pylint: disable-msg=W0232
# pylint: disable-msg=E1101
# pylint: disable-msg=R0903

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

class SiteDownHandler(webapp.RequestHandler):
  """use a redirect so search engines don't index this as our homepage."""
  def get(self):
    """GET handler"""
    self.redirect("/site_down.html")

def main():
  """main function"""
  run_wsgi_app(webapp.WSGIApplication([(r'/.*', SiteDownHandler)], debug=False))

if __name__ == "__main__":
  main()
