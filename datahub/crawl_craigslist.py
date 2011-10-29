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

# TODO: remove silly dependency on dapper.net-- thought I'd need
# it for the full scrape, but ended up not going that way.

"""crawler for craigslist until they provide a real feed."""

from xml.dom import minidom
import sys
import os
import urllib2
import re
import thread
import time
from datetime import datetime

import socket

DEFAULT_TIMEOUT = 10
socket.setdefaulttimeout(DEFAULT_TIMEOUT)

METROS_FN = "craigslist-metros.txt"
CACHE_FN = "craigslist-cache.txt"
pages = {}
page_lock = thread.allocate_lock()
crawlers = 0
crawlers_lock = thread.allocate_lock()
cachefile_lock = thread.allocate_lock()

# set to a lower number if you have problems
MAX_CRAWLERS = 40

def read_metros():
  global metros
  metros = {}
  fh = open(METROS_FN, "r")
  for line in fh:
    url,name = line.split("|")
    metros[url] = name

def crawl_metros():
  #<geo dataType="RawString" fieldName="geo" href="http://waterloo.craigslist.org/" originalElement="a" type="field">waterloo / cedar falls</geo>
  print "getting toplevel geos..."
  fh = urllib2.urlopen("http://www.dapper.net/RunDapp?dappName=craigslistmetros&v=1&applyToUrl=http%3A%2F%2Fgeo.craigslist.org%2Fiso%2Fus")
  geostr = fh.read()
  fh.close()
  dom = minidom.parseString(geostr)
  nodes = dom.getElementsByTagName("geo")
  
  outfh = open(METROS_FN, "w+")
  domains = []
  for node in nodes:
    domain = node.getAttribute("href")
    print "finding submetros within", domain
    fh1 = urllib2.urlopen(domain)
    domain_homepage = fh1.read()  
    fh1.close()  
  
    #<td align="center" colspan="5" id="topban">
    #<div>
    #<h2>new york city</h2>&nbsp;<sup><a href="http://en.wikipedia.org/wiki/New_York_City">w</a></sup>
    #<span class="for"><a href="/mnh/" title="manhattan">mnh</a>&nbsp;<a href="/brk/" title="brooklyn">brk</a>&nbsp;<a href="/que/" title="queens">que</a>&nbsp;<a href="/brx/" title="bronx">brx</a>&nbsp;<a href="/stn/" title="staten island">stn</a>&nbsp;<a href="/jsy/" title="new jersey">jsy</a>&nbsp;<a href="/lgi/" title="long island">lgi</a>&nbsp;<a href="/wch/" title="westchester">wch</a>&nbsp;<a href="/fct/" title="fairfield">fct</a>&nbsp;</span>
    #</div>
    #</td>
    topbanstrs = re.findall(r'<td align="center" colspan="5" id="topban">.+?</td>', domain_homepage, re.DOTALL)
    for topbanstr in topbanstrs:
      links = re.findall(r'<a href="/(.+?)".+?title="(.+?)".+?</a>', topbanstr, re.DOTALL)
      if len(links) > 0:
        for link in links:
          print domain+link[0], ":", link[1]
          outfh.write(domain+link[0]+"|"+link[1]+"\n")
      else:
        names = re.findall(r'<h2>(.+?)</h2>', domain_homepage, re.DOTALL)
        print domain, ":", names[0]
        outfh.write(domain+"|"+names[0]+"\n")
  outfh.close()


def crawl(url, ignore):
  global crawlers, crawlers_lock, pages, page_lock, MAX_CRAWLERS

  if url in pages:
    return

  while crawlers > MAX_CRAWLERS:
    time.sleep(1)

  # we don't care if several wake at once
  crawlers_lock.acquire()
  crawlers = crawlers + 1
  crawlers_lock.release()

  #proxied_url = "http://suprfetch.appspot.com/?url="+urllib2.quote(url+"?for_google_and_craigslist.org_project_footprint_please_dont_block")
  proxied_url = "http://suprfetch.appspot.com/?url="+urllib2.quote(url)

  page = ""
  attempts = 0
  while attempts < 3 and page == "":
    try:
      fh = urllib2.urlopen(proxied_url)
      page = fh.read()
      fh.close()
    except:
      page = ""   # in case close() threw exception
      attempts = attempts + 1
      print "open failed, retry after", attempts, "attempts (url="+url+")"
      time.sleep(1)

  if re.search(r'This IP has been automatically blocked', page, re.DOTALL):
    print "uh oh: craiglist is blocking us (IP blocking).  exiting..."
    sys.exit(1)

  if (re.search(r'sorry.google.com/sorry/', page) or
      re.search(r'to automated requests from a computer virus or spyware', page, re.DOTALL)):
    print "uh oh: google is blocking us (DOS detector).  exiting..."
    sys.exit(1)

  if re.search(r'<TITLE>302 Moved</TITLE>"',page, re.DOTALL):
    newlocstr = re.findall(r'The document has moved <A HREF="(.+?)"',page)          
    print "being redirected to",newlocstr[0]
    crawl(newlocstr[0], "foo")
    return
  
  if attempts >= 3:
    print "crawl failed after 3 attempts:",url
    return

  page_lock.acquire()
  pages[url] = page
  page_lock.release()

  cached_page = re.sub(r'(?:\r?\n|\r)',' ',page)
  cachefile_lock.acquire()
  outfh = open(CACHE_FN, "a")
  outfh.write(url+"-Q-"+cached_page+"\n")
  outfh.close()
  cachefile_lock.release()

  crawlers_lock.acquire()
  crawlers = crawlers - 1
  crawlers_lock.release()

def wait_for_page(url):
  res = ""
  while res == "":
    page_lock.acquire()
    if url in pages:
      res = pages[url]
    page_lock.release()
    if res == "":
      time.sleep(2)
  return res

def sync_fetch(url):
  crawl(url, "")
  if url not in pages:
    print "sync_fetch, failed to crawl url",url
    sys.exit(1)
  return pages[url]


progstart = time.time()
def secs_since_progstart():
  global progstart
  return time.time() - progstart

def crawl_metro_page(url, unused):
  global crawlers, crawlers_lock, pages, page_lock
  listingpage = sync_fetch(url)
  listingurls = re.findall(r'<p><a href="/(.+?)">', listingpage)
  base = re.sub(r'.org/.+', '.org/', url)
  for listing_url in listingurls:
    #print "found",base+listing_url,"in",url
    crawl(base+listing_url, "")
  path = re.sub(r'[^/]+$', '', url)
  nextpages = re.findall(r'<a href="(index[0-9]+[.]html)"', listingpage)
  for nextpage_url in nextpages:
    #print "found",path+nextpage_url,"in",url
    thread.start_new_thread(crawl_metro_page, (path+nextpage_url, ""))

def parse_cache_file(s, listings_only=False, printerrors=True):
  global pages
  for i,line in enumerate(s.splitlines()):
    #print line[0:100]
    res = re.findall(r'^(.+?)-Q-(.+)', line)
    try:
      url,page = res[0][0], res[0][1]
      if (not listings_only or re.search(r'html$', url)):
        pages[url] = page
    except:
      if printerrors:
        print print datetime.now(), "error parsing cache file on line", i+1
        #print line
    
def load_cache():
  global CACHE_FN
  try:
    fh = open(CACHE_FN, "r")
    instr = fh.read()
    print "closing cache file", CACHE_FN
    fh.close()
    print "parsing cache data", len(instr), "bytes"
    parse_cache_file(instr, False)
    print "loaded", len(pages), "pages."
  except:
    # ignore errors if file doesn't exist
    pass

def print_status():
  global pages, num_cached_pages, crawlers
  samesame = 0
  last_crawled_pages = 0
  while True:
    crawled_pages = len(pages) - num_cached_pages
    pages_per_sec = int(crawled_pages/secs_since_progstart())
    msg = str(secs_since_progstart())+": main thread: "
    msg += "waiting for " + str(crawlers) + " crawlers.\n"
    msg += str(crawled_pages) + " pages crawled so far"
    msg += "(" + str(pages_per_sec) + " pages/sec). "
    msg += str(len(pages)) + " total pages."
    print msg
    if last_crawled_pages == crawled_pages:
      samesame += 1
      if samesame >= 100:
        print "done (waited long enough)."
        break
    else:
      last_crawled_pages = crawled_pages
    time.sleep(2)

from optparse import OptionParser
if __name__ == "__main__":
  parser = OptionParser("usage: %prog [options]...")
  parser.set_defaults(metros=False)
  parser.set_defaults(load_cache=True)
  parser.add_option("--metros", action="store_true", dest="metros")
  parser.add_option("--load_cache", action="store_true", dest="load_cache")
  parser.add_option("--noload_cache", action="store_false", dest="load_cache")
  (options, args) = parser.parse_args(sys.argv[1:])

  if options.metros:
    crawl_metros()

  read_metros()
  if options.load_cache:
    load_cache()
  else:
    try:
      os.unlink(CACHE_FN)
    except:
      pass

  num_cached_pages = len(pages)

  outstr = ""
  for url in metros:
    thread.start_new_thread(crawl_metro_page, (url+"vol/", ""))

  print_status()
  sys.exit(0)
