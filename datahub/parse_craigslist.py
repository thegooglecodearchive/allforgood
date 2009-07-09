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
parser for craigslist custom crawl-- not FPXML
"""

# note: this is designed to consume the output from the craigslist crawler
# example record
#http://limaohio.craigslist.org/vol/1048151556.html-Q-<!DOCTYPE html PUBLIC
# "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose
#.dtd"> <html> <head> 	<title>Foster Parents Needed</title> 	<meta name="ro
#bots" content="NOARCHIVE"> 	<link rel="stylesheet" title="craigslist" href=
#"http://www.craigslist.org/styles/craigslist.css" type="text/css" media="al
#l"> </head>   <body onload="initFlag(1048151556)" class="posting">  <div cl
#ass="bchead"> <a id="ef" href="/email.friend?postingID=1048151556">email th
#is posting to a friend</a> <a href="http://limaohio.craigslist.org">lima / 
#findlay craigslist</a>         &gt;  <a href="/vol/">volunteers</a> </div> 
# 	<div id="flags"> 		<div id="flagMsg"> 			please <a href="http://www.craig
#slist.org/about/help/flags_and_community_moderation">flag</a> with care: 		
#</div> 		<div id="flagChooser"> 			<br> 			<a class="fl" id="flag16" href="
#/flag/?flagCode=16&amp;postingID=1048151556" 				title="Wrong category, wro
#ng site, discusses another post, or otherwise misplaced"> 				miscategorize
#d</a> 			<br>  			<a class="fl" id="flag28" href="/flag/?flagCode=28&amp;po
#stingID=1048151556" 				title="Violates craigslist Terms Of Use or other po
#sted guidelines"> 				prohibited</a> 			<br>  			<a class="fl" id="flag15" 
#href="/flag/?flagCode=15&amp;postingID=1048151556" 				title="Posted too fr
#equently, in multiple cities/categories, or is too commercial"> 				spam/ov
#erpost</a> 			<br>  			<a class="fl" id="flag9" href="/flag/?flagCode=9&amp
#;postingID=1048151556" 				title="Should be considered for inclusion in the
# Best-Of-Craigslist"> 				best of craigslist</a> 			<br> 		</div> 	</div>  
#   <h2>Foster Parents Needed (Northwest Ohio)</h2> <hr> Reply to: <a href="
#mailto:&#99;&#111;&#109;&#109;&#45;&#49;&#48;&#52;&#56;&#49;&#53;&#49;&#53;
#&#53;&#54;&#64;&#99;&#114;&#97;&#105;&#103;&#115;&#108;&#105;&#115;&#116;&#
#46;&#111;&#114;&#103;?subject=Foster%20Parents%20Needed%20(Northwest%20Ohio
#)">&#99;&#111;&#109;&#109;&#45;&#49;&#48;&#52;&#56;&#49;&#53;&#49;&#53;&#53
#;&#54;&#64;&#99;&#114;&#97;&#105;&#103;&#115;&#108;&#105;&#115;&#116;&#46;&
##111;&#114;&#103;</a> <sup>[<a href="http://www.craigslist.org/about/help/r
#eplying_to_posts" target="_blank">Errors when replying to ads?</a>]</sup><b
#r> Date: 2009-02-24,  8:37AM EST<br> <br> <br> <div id="userbody"> Diversio
#n Adolescent Foster Care of Ohio is accepting applications for foster paren
#ts in our Findlay office.  There are many children in Ohio in need of a tem
#porary place to call home. Foster parent training is currently being offere
#d.  Please call Stacy for more information 800-824-3007.  We look forward t
#o meeting with you. www.diversionfostercare.org <br>  		<table> 			<tr> 			
#	<td></td> 				<td></td> 			</tr> 			<tr> 				<td></td> 				<td></td> 			</
#tr> 		</table>    <br><br><ul> <li> Location: Northwest Ohio <li>it's NOT o
#k to contact this poster with services or other commercial interests</ul>  
#</div> PostingID: 1048151556<br>   <br> <hr> <br>  <div class="clfooter">  
#       Copyright &copy; 2009 craigslist, inc.&nbsp;&nbsp;&nbsp;&nbsp;<a hre
#f="http://www.craigslist.org/about/terms.of.use.html">terms of use</a>&nbsp
#;&nbsp;&nbsp;&nbsp;<a href="http://www.craigslist.org/about/privacy_policy"
#>privacy policy</a>&nbsp;&nbsp;&nbsp;&nbsp;<a href="/forums/?forumID=8">fee
#dback forum</a> </div> <script type="text/javascript" src="http://www.craig
#slist.org/js/jquery.js"></script> <script type="text/javascript" src="http:
#//www.craigslist.org/js/postings.js"></script> </body> </html>  
import sys
import re
import xml.sax.saxutils
import xml_helpers as xmlh
import crawl_craigslist
from datetime import datetime

import dateutil.parser

CL_LATLONGS = None

def load_craigslist_latlongs():
  """map of craigslist sub-metros to their latlongs."""
  global CL_LATLONGS
  CL_LATLONGS = {}
  latlongs_fh = open('craigslist-metro-latlongs.txt')
  for line in latlongs_fh:
    line = re.sub(r'\s*#.*$', '', line).strip()
    if line == "":
      continue
    try:
      url, lat, lng = line.strip().split("|")
    except:
      print "error parsing line", line
      sys.exit(1)
    CL_LATLONGS[url] = lat + "," + lng
  latlongs_fh.close()

def extract(instr, rx):
  """find the first instance of rx in instr and strip it of whitespace."""
  res = re.findall(rx, instr, re.DOTALL)
  if len(res) > 0:
    return res[0].strip()
  return ""

# pylint: disable-msg=R0915
def parse(instr, maxrecs, progress):
  """return FPXML given craigslist data"""
  if CL_LATLONGS == None:
    load_craigslist_latlongs()
  xmlh.print_progress("loading craigslist crawler output...")
  crawl_craigslist.parse_cache_file(instr, listings_only=True)
  xmlh.print_progress("loaded "+str(len(crawl_craigslist.pages))+" craigslist pages.")

  # convert to footprint format
  outstr = '<?xml version="1.0" ?>'
  outstr += '<FootprintFeed schemaVersion="0.1">'
  outstr += '<FeedInfo>'
  outstr += xmlh.output_val('providerID', "105")
  outstr += xmlh.output_val('providerName', "craigslist")
  outstr += xmlh.output_val('feedID', "craigslist")
  outstr += xmlh.output_val('createdDateTime', xmlh.current_ts())
  outstr += xmlh.output_val('providerURL', "http://www.craigslist.org/")
  outstr += '</FeedInfo>'

  numorgs = numopps = 0

  # no "organization" in craigslist postings
  outstr += '<Organizations>'
  outstr += '<Organization>'
  outstr += '<organizationID>0</organizationID>'
  outstr += '<nationalEIN></nationalEIN>'
  outstr += '<name></name>'
  outstr += '<missionStatement></missionStatement>'
  outstr += '<description></description>'
  outstr += '<location>'
  outstr += xmlh.output_val("city", "")
  outstr += xmlh.output_val("region", "")
  outstr += xmlh.output_val("postalCode", "")
  outstr += '</location>'
  outstr += '<organizationURL></organizationURL>'
  outstr += '<donateURL></donateURL>'
  outstr += '<logoURL></logoURL>'
  outstr += '<detailURL></detailURL>'
  outstr += '</Organization>'
  numorgs += 1
  outstr += '</Organizations>'

  skipped_listings = {}
  skipped_listings["body"] = skipped_listings["title"] = \
      skipped_listings["not-ok"] = 0
  outstr += '<VolunteerOpportunities>'
  for i, url in enumerate(crawl_craigslist.pages):
    page = crawl_craigslist.pages[url]

    ok = extract(page, "it's OK to distribute this "+
                 "charitable volunteerism opportunity")
    if ok == "":
      skipped_listings["not-ok"] += 1
      continue

    title = extract(page, "<title>(.+?)</title>")
    if title == "":
      skipped_listings["title"] += 1
      continue

    body = extract(page, '<div id="userbody">(.+?)<')
    if len(body) < 25:
      skipped_listings["body"] += 1
      continue

    item_id = extract(url, "/vol/(.+?)[.]html$")
    locstr = extract(page, "Location: (.+?)<")
    datestr = extract(page, "Date: (.+?)<")
    ts = dateutil.parser.parse(datestr)
    datetimestr = ts.strftime("%Y-%m-%dT%H:%M:%S")
    datestr = ts.strftime("%Y-%m-%d")


    if (maxrecs>0 and i>maxrecs):
      break
    xmlh.print_rps_progress("opps", progress, i, maxrecs)
    if progress and i > 0 and i % 250 == 0:
      msg = "skipped " + str(skipped_listings["title"]+skipped_listings["body"])
      msg += " listings ("+str(skipped_listings["title"]) + " for no-title and "
      msg += str(skipped_listings["body"]) + " for short body and "
      msg += str(skipped_listings["not-ok"]) + " for no-redistrib)"
      xmlh.print_progress(msg)
      #print "---"
      #print "title:",title
      #print "loc:",locstr
      #print "date:",datestr
      #print "body:",body[0:100]

    outstr += '<VolunteerOpportunity>'
    outstr += '<volunteerOpportunityID>%s</volunteerOpportunityID>' % (item_id)
    outstr += '<sponsoringOrganizationIDs><sponsoringOrganizationID>0</sponsoringOrganizationID></sponsoringOrganizationIDs>'
    outstr += '<volunteerHubOrganizationIDs><volunteerHubOrganizationID>0</volunteerHubOrganizationID></volunteerHubOrganizationIDs>'
    outstr += '<title>%s</title>' % (title)
    outstr += '<detailURL>%s</detailURL>' % (url)
    # avoid CDATA in body...
    esc_body = xml.sax.saxutils.escape(body)
    esc_body100 = xml.sax.saxutils.escape(body[0:100])
    outstr += '<description>%s</description>' % (esc_body)
    outstr += '<abstract>%s</abstract>' % (esc_body100 + "...")
    outstr += '<lastUpdated>%s</lastUpdated>' % (datetimestr)
    # TODO: expires
    # TODO: synthesize location from metro...
    outstr += '<locations><location>'
    outstr += '<name>%s</name>' % (xml.sax.saxutils.escape(locstr))
    # what about the few that do geocode?
    lat, lng = "", ""
    try:
      domain, unused = url.split("vol/")
      lat, lng = CL_LATLONGS[domain].split(",")
    except:
      # ignore for now
      #print url
      #continue
      pass
    outstr += '<latitude>%s</latitude>' % (lat)
    outstr += '<longitude>%s</longitude>' % (lng)
    outstr += '</location></locations>'
    #outstr += '<locations><location>'
    #outstr += '<city>%s</city>' % (
    #outstr += '<region>%s</region>' % (
    #outstr += '</location></locations>'
    outstr += '<dateTimeDurations><dateTimeDuration>'
    outstr += '<openEnded>No</openEnded>'
    outstr += '<startDate>%s</startDate>' % (datestr)
    # TODO: endDate = startDate + N=14 days?
    # TODO: timezone???
    #outstr += '<endDate>%s</endDate>' % (
    outstr += '</dateTimeDuration></dateTimeDurations>'
    # TODO: categories???
    #outstr += '<categoryTags>'
    outstr += '</VolunteerOpportunity>'
    numopps += 1
  outstr += '</VolunteerOpportunities>'
  outstr += '</FootprintFeed>'

  #outstr = re.sub(r'><([^/])', r'>\n<\1', outstr)
  return outstr, numorgs, numopps
