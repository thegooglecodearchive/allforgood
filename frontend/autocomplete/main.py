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
main() for autocomplete handler
"""

# view classes aren inherently not pylint-compatible
# pylint: disable-msg=C0103
# pylint: disable-msg=W0232
# pylint: disable-msg=E1101
# pylint: disable-msg=R0903

import os
import logging
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

AUTOCOMPLETE_FILENAME = "popular_words.txt"

POPULAR_WORDS = None
DEFAULT_MAXRESULTS = 10
MAX_MAXRESULTS = 100

class Query(webapp.RequestHandler):
  """prefix query on autocomplete."""
  def get(self):
    """HTTP get method."""
    global POPULAR_WORDS

    reload_words = self.request.get('reload_words')
    if POPULAR_WORDS == None or reload_words == "1":
      logging.info("reloading words...")
      POPULAR_WORDS = []
      path = os.path.join(os.path.dirname(__file__), AUTOCOMPLETE_FILENAME)
      fh = open(path, 'r')
      for line in fh:
        count, word = line.rstrip('\n\r').split("\t")
        count = count  # shutup pylint
        POPULAR_WORDS.append(word)
      logging.info("loaded %d words." % len(POPULAR_WORDS))

    querystr = self.request.get('q') or ""
    querystr = querystr.strip().lower()
    if querystr == "":
      self.response.headers['Content-Type'] = 'text/plain'
      self.response.out.write("please provide &q= to query the autocompleter.")
      return
      
    maxresultstr = self.request.get('maxresults')
    try:
      maxwords = int(maxresultstr)
    except:
      maxwords = DEFAULT_MAXRESULTS
    if maxwords > MAX_MAXRESULTS:
      maxwords = MAX_MAXRESULTS
    elif maxwords < 1:
      maxwords = 1

    outstr = ""
    numresults = 0
    for word in POPULAR_WORDS:
      if word.find(querystr) == 0:
        outstr += word + "\n"
        numresults += 1
        if numresults >= maxwords:
          break
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.out.write(outstr)

APP = webapp.WSGIApplication(
  [('/autocomplete/query', Query)],
  debug=True)

def main():
  """main for standalone execution."""
  run_wsgi_app(APP)

if __name__ == "__main__":
  main()
