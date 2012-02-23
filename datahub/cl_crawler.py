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

"""crawler for craigslist until they provide a real feed."""

from optparse import OptionParser
from xml.dom import minidom
import sys
import os
import urllib2
import re
import thread
import time
from datetime import datetime
import socket
import string
import geocoder
import xml_helpers as xmlh

import utf8

NUMOPPS = 0
DEFAULT_TIMEOUT = 10
socket.setdefaulttimeout(DEFAULT_TIMEOUT)

MAX_THREADS = 10
THREADS = 0
CACHE_DIR = "craigslist/"
METROS = CACHE_DIR + "index.txt"
SPACER = "==================================="


def get_cache_file(file, ext = ""):
  defang = re.sub(r"&[a-z]+;", "", file)
  return CACHE_DIR + defang + ext


def get_metro_cache_file(url):
  file = url[7:]
  ar = file.split(".")
  file = ar[0]
  return get_cache_file(file, ".metro")


def get_opp_file(url):
  file = extract(url, "/vol/(.+?)[.]html$")
  return get_cache_file(file, ".xml")


def fetch_metro_threaded(metro, my_thread):
  global THREADS
  url = metro["url"] + "/search/vol/?query=+&format=rss"

  rss = ""
  retry = 3
  while not rss and retry > 0:
    try:
      finp = urllib2.urlopen(url)
      rss = finp.read()
      finp.close()
      break
    except:
      time.sleep(10 / retry)
      retry -= 1

  file = get_metro_cache_file(url)
  fout = open(file, "w")
  if fout:
    fout.write(metro["url"] + "\n")
    fout.write(metro["name"] + "\n")
    fout.write(metro["location"] + "\n")
    fout.write(metro["latlng"] + "\n")
    fout.write(SPACER + "\n")
    fout.write(rss)
    fout.close()

  if THREADS > 0:
    THREADS -= 1


def geocode_craigslist_domain(location, domain):
  if domain == "mobile":
    location = "Mobile, Al"
  elif domain == "wheeling":
    location = "wheeling, WV"

  rsp = geocoder.geocode_call(location + ", US")
  if not rsp:
    rsp = geocoder.geocode_call(domain + ", US")
    if not rsp:
      rsp = ["???", "0", "0", "0"]
  #["Auburn, AL", "32.6098566", "-85.4807825", "4"]
  return rsp 


def fetch_metros(refresh = False):
  metros = []
  if refresh:
    print "refreshing cache of craigslist local sites..."
    html = ""
    fh = urllib2.urlopen("http://www.craigslist.org/about/sites")
    if fh:
      html = fh.read()
      fh.close()

    in_US = False
    lines = html.split("\n")
    for line in lines:
      if not in_US:
        # <h1 class="continent_header"><a name="US"></a>US</h1>
        if line.find("continent_header") >= 0:
          in_US = True
        continue

      if line.find("continent_header") >= 0:
        # outside of US
        break

      #<li><a href="http://auburn.craigslist.org">auburn</a></li>
      if line.find("<li><a href") >= 0:
        # we are going to make a line like this http://...|name|location|lat,lng
        ar = line.split('"')
        url = ar[1]
        # TODO: replace with a clever regex thing
        ar = line.split('<a href="', 1)
        ar = re.split(r"<\/a>", ar[1])
        ar = ar[0].split(">")
        name = ar[1]
        #["Auburn, AL", "32.6098566", "-85.4807825", "4"]
        #location, lat, lng, acc = geocode_craigslist_domain(url)
        subdomain = url[7:].replace(".craigslist.org", "")
        location, lat, lng, acc = geocode_craigslist_domain(name, subdomain)
        print "metro: " + url + " is " +  location
        metros.append({"url":url, "name":name, "location": location, "latlng":lat + "," + lng})

    outfh = open(METROS, "w")
    if outfh:
      for metro in metros:
        outfh.write(metro["url"] + "|")
        outfh.write(metro["name"] + "|")
        outfh.write(metro["location"] + "|")
        outfh.write(metro["latlng"] + "\n")
      outfh.close()

  print "loading list of craigslist local sites..."
  fh = open(METROS, "r")
  if fh:
    for line in fh:
      url, name, location, latlng = line.split("|")
      metros.append({"url":url, "name":name, "location":location, "latlng":latlng})
    fh.close()

  return metros


def init_footprint_xml():
  outstr = '<?xml version="1.0" ?>'
  outstr += '<FootprintFeed schemaVersion="0.1">'
  outstr += "<FeedInfo>"
  outstr += xmlh.output_val("providerID", "105")
  outstr += xmlh.output_val("providerName", "craigslist")
  outstr += xmlh.output_val("feedID", "craigslist")
  outstr += xmlh.output_val("createdDateTime", xmlh.current_ts())
  outstr += xmlh.output_val("providerURL", "http://www.craigslist.org/")
  outstr += "</FeedInfo>"
  # no "organization" in craigslist postings
  outstr += "<Organizations>"
  outstr += "<Organization>"
  outstr += "<organizationID>0</organizationID>"
  outstr += "<nationalEIN></nationalEIN>"
  outstr += "<name></name>"
  outstr += "<missionStatement></missionStatement>"
  outstr += "<description></description>"
  outstr += "<location>"
  outstr += xmlh.output_val("city", "")
  outstr += xmlh.output_val("region", "")
  outstr += xmlh.output_val("postalCode", "")
  outstr += "</location>"
  outstr += "<organizationURL></organizationURL>"
  outstr += "<donateURL></donateURL>"
  outstr += "<logoURL></logoURL>"
  outstr += "<detailURL></detailURL>"
  outstr += "</Organization>"
  outstr += "</Organizations>"
  outstr += "<VolunteerOpportunities>"
  return outstr


def extract(instr, rx):
  """find the first instance of rx in instr and strip it of whitespace."""
  res = re.findall(rx, instr, re.DOTALL)
  if len(res) > 0:
    return res[0].strip()
  return ""

def accum_opp_xml(file):
  rtn = ""
  if file.find(".xml") > 0:
    fh = open(file)
    if fh:
      rtn = fh.read()
      fh.close()
  return rtn
    

def write_opp_xml(title, body, detail_url, location, latlng):
  global NUMOPPS
  ts = datetime.now()
  datetimestr = ts.strftime("%Y-%m-%dT%H:%M:%S")
  datestr = ts.strftime("%Y-%m-%d")

  item_id = extract(detail_url, "/vol/(.+?)[.]html$")
  title = re.sub(r"&[a-z]+;", "", title)
  body = re.sub(r"&[a-z]+;", "", body)
  ar = latlng.split(",")
  lat = ar[0]
  lng = ar[1]

  outstr = "<VolunteerOpportunity>"
  outstr += "<volunteerOpportunityID>%s</volunteerOpportunityID>" % (item_id)
  outstr += "<sponsoringOrganizationIDs>"
  outstr += "<sponsoringOrganizationID>0</sponsoringOrganizationID>"
  outstr += "</sponsoringOrganizationIDs>"
  outstr += "<volunteerHubOrganizationIDs>"
  outstr += "<volunteerHubOrganizationID>0</volunteerHubOrganizationID>"
  outstr += "</volunteerHubOrganizationIDs>"
  outstr += "<title><![CDATA[%s]]></title>" % (title)
  outstr += "<detailURL>%s</detailURL>" % (detail_url)
  outstr += "<description><![CDATA[%s]]></description>" % (body)
  outstr += "<abstract><![CDATA[%s]]></abstract>" % (body[:100] + "...")
  outstr += "<lastUpdated>%s</lastUpdated>" % (datetimestr)
  outstr += "<locations>"
  outstr += "<location>"
  outstr += "<name>%s</name>" % (location)
  outstr += "<latitude>%s</latitude>" % (lat)
  outstr += "<longitude>%s</longitude>" % (lng)
  outstr += "</location>"
  outstr += "</locations>"
  outstr += "<dateTimeDurations><dateTimeDuration>"
  outstr += "<openEnded>No</openEnded>"
  outstr += "<startDate>%s</startDate>" % (datestr)
  outstr += "</dateTimeDuration></dateTimeDurations>"
  outstr += "</VolunteerOpportunity>"

  file = get_opp_file(detail_url)
  fh = open(file, "w")
  if fh:
    fh.write(outstr)
    fh.close()
    NUMOPPS += 1


def strip_tags(str):
  import re
  p = re.compile(r"<.*?>")
  return p.sub("", str)


def get_xml_text(nodelist):
  rtn = ""
  for node in nodelist:
    if node.nodeType == node.ELEMENT_NODE:
      rtn += get_xml_text(node)
    elif node.nodeType == node.TEXT_NODE or node.nodeType == node.CDATA_SECTION_NODE:
      rtn += node.data
  return rtn


def parse_metro_threaded(file, my_thread):
  global THREADS
  buff = ""
  try:
    fh = open(file, "r")
    if fh:
      buff = fh.read()
      fh.close()
  except:
    pass

  if buff:
    lines = buff.split("\n")
    url = lines.pop(0)
    name = lines.pop(0)
    location = lines.pop(0)
    latlng = lines.pop(0)
    lines.pop(0)
    lines.pop(0) # delimiter
    print "thread #" + str(my_thread) + ":" + url
    rss = "\n".join(lines) # just the page

    try:
      feed_content = unicode(rss, "utf-8", "ignore")
      feed = minidom.parseString(feed_content.encode("utf-8"))
      items = feed.getElementsByTagName("item")
    except:
      items = []

    for item in items:
      try:
        title = strip_tags(get_xml_text(item.getElementsByTagName("title")[0].childNodes)).strip()
        detail_url = get_xml_text(item.getElementsByTagName("link")[0].childNodes).strip()
        desc = strip_tags(get_xml_text(item.getElementsByTagName("description")[0].childNodes)).strip()
        desc = desc.replace("\n", " ")
        desc = desc.replace("\r", "")
        write_opp_xml(title, desc, detail_url, location, latlng)
      except:
        pass

  if THREADS > 0:
    THREADS -= 1


if __name__ == "__main__":
  parser = OptionParser("usage: %prog [options]...")
  parser.set_defaults(metros=False)
  parser.add_option("--index", action="store_true", dest="index")
  parser.add_option("--fetch", action="store_true", dest="fetch")
  parser.add_option("--parse", action="store_true", dest="parse")
  parser.add_option("--accum", action="store_true", dest="accum")
  (options, args) = parser.parse_args(sys.argv[1:])

  if options.index or options.fetch or options.parse:
    try:
      os.mkdir(CACHE_DIR)
    except:
      pass

    metros = fetch_metros(options.index)
    if options.fetch:
      THREADS = 0
      while len(metros):
        if THREADS >= MAX_THREADS:
          print "waiting for index thread to become available..."
          time.sleep(3)
        else:
          THREADS += 1
          metro = metros.pop(0)
          print "indexing " + metro["url"]
          thread.start_new_thread(fetch_metro_threaded, (metro, THREADS))
      if options.parse:
        metros = fetch_metros()

    if options.parse:
      THREADS = 0
      while len(metros):
        if THREADS >= MAX_THREADS:
          print "waiting for parse thread to become available..."
          time.sleep(3)
        else:
          THREADS += 1
          metro = metros.pop(0)
          print "parsing " + metro["url"]
          thread.start_new_thread(parse_metro_threaded, (get_metro_cache_file(metro["url"]), THREADS))


  if options.accum:
    xml = init_footprint_xml()
    NUMOPS = 0
    for file in os.listdir(CACHE_DIR):
      NUMOPPS += 1
      xml += accum_opp_xml(CACHE_DIR + file)
    xml += "</VolunteerOpportunities></FootprintFeed>"
    fh = open("craigslist.xml", "w")
    fh.write(xml)
    fh.close()
  
  if options.accum or options.parse:
    print "num opps: " + str(NUMOPPS)
