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

"""
parser for usaservice.org
"""
import xml_helpers as xmlh
import re
from datetime import datetime

import dateutil.parser

# pylint: disable-msg=R0915
def parse(instr, maxrecs, progress):
  """return FPXML given usaservice data"""
  # TODO: progress
  known_elnames = [ 'channel', 'db:abstract', 'db:address', 'db:attendee_count', 'db:categories', 'db:city', 'db:country', 'db:county', 'db:dateTime', 'db:event', 'db:eventType', 'db:guest_total', 'db:host', 'db:latitude', 'db:length', 'db:longitude', 'db:rsvp', 'db:scheduledTime', 'db:state', 'db:street', 'db:title', 'db:venue_name', 'db:zipcode', 'description', 'docs', 'guid', 'item', 'language', 'link', 'pubDate', 'rss', 'title', ]

  # convert to footprint format
  s = '<?xml version="1.0" ?>'
  s += '<FootprintFeed schemaVersion="0.1">'
  s += '<FeedInfo>'
  # TODO: assign provider IDs?
  s += '<providerID>101</providerID>'
  s += '<providerName>usaservice.org</providerName>'
  s += '<feedID>1</feedID>'
  s += '<createdDateTime>%s</createdDateTime>' % xmlh.current_ts()
  s += '<providerURL>http://www.usaservice.org/</providerURL>'
  s += '<description>Syndicated events</description>'
  # TODO: capture ts -- use now?!
  s += '</FeedInfo>'

  numorgs = numopps = 0
  # hardcoded: Organization
  s += '<Organizations>'
  s += '<Organization>'
  s += '<organizationID>0</organizationID>'
  s += '<nationalEIN></nationalEIN>'
  s += '<name></name>'
  s += '<missionStatement></missionStatement>'
  s += '<description></description>'
  s += '<location><city></city><region></region><postalCode></postalCode></location>'
  s += '<organizationURL></organizationURL>'
  s += '<donateURL></donateURL>'
  s += '<logoURL></logoURL>'
  s += '<detailURL></detailURL>'
  s += '</Organization>'
  numorgs += 1
  s += '</Organizations>'
    
  s += '<VolunteerOpportunities>'

  instr = re.sub(r'<(/?db):', r'<\1_', instr)
  for i, line in enumerate(instr.splitlines()):
    if (maxrecs>0 and i>maxrecs):
      break
    xmlh.print_rps_progress("opps", progress, i, maxrecs)
    item = xmlh.simple_parser(line, known_elnames, progress=False)

    # unmapped: db_rsvp  (seems to be same as link, but with #rsvp at end of url?)
    # unmapped: db_host  (no equivalent?)
    # unmapped: db_county  (seems to be empty)
    # unmapped: attendee_count
    # unmapped: guest_total
    # unmapped: db_title   (dup of title, above)
    s += '<VolunteerOpportunity>'
    s += '<volunteerOpportunityID>%s</volunteerOpportunityID>' % (xmlh.get_tag_val(item, "guid"))
    # hardcoded: sponsoringOrganizationID
    s += '<sponsoringOrganizationIDs><sponsoringOrganizationID>0</sponsoringOrganizationID></sponsoringOrganizationIDs>'
    # hardcoded: volunteerHubOrganizationID
    s += '<volunteerHubOrganizationIDs><volunteerHubOrganizationID>0</volunteerHubOrganizationID></volunteerHubOrganizationIDs>'
    s += '<title>%s</title>' % (xmlh.get_tag_val(item, "title"))
    s += '<abstract>%s</abstract>' % (xmlh.get_tag_val(item, "abstract"))
    s += '<volunteersNeeded>-8888</volunteersNeeded>'

    dbscheduledTimes = item.getElementsByTagName("db_scheduledTime")
    if (dbscheduledTimes.length != 1):
      print datetime.now(), "parse_usaservice: only 1 db_scheduledTime supported."
      return None
    dbscheduledTime = dbscheduledTimes[0]
    s += '<dateTimeDurations><dateTimeDuration>'
    length = xmlh.get_tag_val(dbscheduledTime, "db_length")
    if length == "" or length == "-1":
      s += '<openEnded>Yes</openEnded>'
    else:
      s += '<openEnded>No</openEnded>'
    date, time = xmlh.get_tag_val(dbscheduledTime, "db_dateTime").split(" ")
    s += '<startDate>%s</startDate>' % (date)
    # TODO: timezone???
    s += '<startTime>%s</startTime>' % (time)
    s += '</dateTimeDuration></dateTimeDurations>'

    dbaddresses = item.getElementsByTagName("db_address")
    if (dbaddresses.length != 1):
      print datetime.now(), "parse_usaservice: only 1 db_address supported."
      return None
    dbaddress = dbaddresses[0]
    s += '<locations><location>'
    s += '<name>%s</name>' % (xmlh.get_tag_val(item, "db_venue_name"))
    s += '<streetAddress1>%s</streetAddress1>' % (xmlh.get_tag_val(dbaddress, "db_street"))
    s += '<city>%s</city>' % (xmlh.get_tag_val(dbaddress, "db_city"))
    s += '<region>%s</region>' % (xmlh.get_tag_val(dbaddress, "db_state"))
    s += '<country>%s</country>' % (xmlh.get_tag_val(dbaddress, "db_country"))
    s += '<postalCode>%s</postalCode>' % (xmlh.get_tag_val(dbaddress, "db_zipcode"))
    s += '<latitude>%s</latitude>' % (xmlh.get_tag_val(item, "db_latitude"))
    s += '<longitude>%s</longitude>' % (xmlh.get_tag_val(item, "db_longitude"))
    s += '</location></locations>'

    type = xmlh.get_tag_val(item, "db_eventType")
    s += '<categoryTags><categoryTag>%s</categoryTag></categoryTags>' % (type)

    s += '<contactName>%s</contactName>' % xmlh.get_tag_val(item, "db_host")
    s += '<detailURL>%s</detailURL>' % (xmlh.get_tag_val(item, "link"))
    s += '<description>%s</description>' % (xmlh.get_tag_val(item, "description"))
    pubdate = xmlh.get_tag_val(item, "pubDate")
    if re.search("[0-9][0-9] [A-Z][a-z][a-z] [0-9][0-9][0-9][0-9]", pubdate):
      # TODO: parse() is ignoring timzone...
      ts = dateutil.parser.parse(pubdate)
      pubdate = ts.strftime("%Y-%m-%dT%H:%M:%S")
    s += '<lastUpdated>%s</lastUpdated>' % (pubdate)
    s += '</VolunteerOpportunity>'
    numopps += 1
    
  s += '</VolunteerOpportunities>'
  s += '</FootprintFeed>'
  #s = re.sub(r'><([^/])', r'>\n<\1', s)
  return s, numorgs, numopps

