#!/usr/bin/python
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

#http://usaservice.org/page/event/search_results?orderby=day&state=CA&country=US&event_type%5b%5d=&limit=1000&radius_unit=miles&format=commons_rss&wrap=no

from xml.dom import minidom
import sys
import os
import urllib
import re
import thread
import time
from datetime import datetime
import socket

DEFAULT_TIMEOUT = 30
socket.setdefaulttimeout(DEFAULT_TIMEOUT)

STATES = ['AA','AE','AK','AL','AP','AR','AS','AZ','CA','CO','CT','DC','DE','FL','FM','GA','GU','HI','IA','ID','IL','IN','KS','KY','LA','MA','MD','ME','MH','MI','MN','MO','MP','MS','MT','NC','ND','NE','NH','NJ','NM','NV','NY','OH','OK','OR','PA','PR','PW','RI','SC','SD','TN','TX','UT','VA','VI','VT','WA','WI','WV','WY','AB','BC','MB','NB','NL','NT','NS','NU','ON','PE','QC','SK','YT','na']

OUTPUT_FN = "usaservice.txt"
file_lock = thread.allocate_lock()

crawlers = 0
crawlers_lock = thread.allocate_lock()

def get_url(state):
  url = "http://usaservice.org/page/event/search_results?orderby=day&state="
  url += state+"&country=US&event_type%5b%5d=&limit=1000&radius_unit=miles&format=commons_rss&wrap=no"
  return url

def crawl_state(state, ignore):
  global crawlers, crawlers_lock, OUTPUT_FN, file_lock

  crawlers_lock.acquire()
  crawlers = crawlers + 1
  crawlers_lock.release()

  while crawlers > 10:
    time.sleep(1)

  try:
    url = get_url(state)
    fh = urllib.urlopen(url)
    rss = fh.read()
    fh.close()

    items = re.findall(r'<item>.+?</item>', rss, re.DOTALL)
    if len(items) > 0:
      print datetime.now(), "found", len(items), "items for state", state
      outstr = ""
      for item in items:
        item = re.sub(r'(?:\r?\n|\r)',' ', item)
        if re.search(r'Find Money For Next 12 Months', item):
          continue
        outstr += item + "\n"
      file_lock.acquire()
      outfh = open(OUTPUT_FN, "a")
      outfh.write(outstr)
      outfh.close()
      file_lock.release()
  except:
    pass

  crawlers_lock.acquire()
  crawlers = crawlers - 1
  crawlers_lock.release()

from optparse import OptionParser
if __name__ == "__main__":
  try:
    os.unlink(OUTPUT_FN)
  except:
    pass

  for state in STATES:
    thread.start_new_thread(crawl_state, (state, "foo"))
  # give them a chance to start
  time.sleep(1)

  while (crawlers > 0):
    print datetime.now(), "waiting for", crawlers, "crawlers to finish."
    time.sleep(1)

  sys.exit(0)
