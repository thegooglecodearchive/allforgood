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
parser for 350.org custom feed -- not FPXML
"""

# example record
"""
<node>
<Nid>18936</Nid>
<Country>United States</Country>
<Province>Massachusetts</Province>
<City>Amherst</City>
<title>Carbon Reduction Instruction Event</title>
<Body>
<p>HELPERS NEEDED!!!! We are attempting to put together an informational event on the common which will include some direct action such as building solar ovens, writing political letters, and spreading information about all the positive work that is being done and can be done locally, including at our local colleges/university.</p>
</Body>
<Latitude></Latitude>
<Longitude></Longitude>
<Link>http://www.350.org/node/18936</Link>
<Start_Date>YYYY-MM-DDT12:00</Start_Date>
<End_Date>YYYY-MM-DDT15:00</End_Date>
</node>
"""
import sys
import re
import xml.sax.saxutils
import xml_helpers as xmlh
from datetime import datetime
import dateutil.parser

import utf8

# pylint: disable-msg=R0915
def parse(instr, maxrec, progress):
  """return FPXML given 350.org data"""
  feed = xmlh.parse_or_die(instr.encode('utf-8'))

  org_id = str(139)
  mission_statement = "350.org is an international campaign that's building a movement to unite the world around solutions to the climate crisis--the solutions that science and justice demand."
  org_desc = "On October 10 we'll be helping host a Global Work Party, with thousands of communities setting up solar panels or digging community gardens or laying out bike paths."

  start_date = '2010-10-01'
  today = datetime.now()
  last_updated = today.strftime("%Y-%m-%dT%H:%M:%S")

  numorgs = 1
  numopps = 0
  xmlh.print_progress("loading 350.org custom XML...")

  # convert to footprint format
  outstr = '<?xml version="1.0" ?>'
  outstr += '<FootprintFeed schemaVersion="0.1">'
  outstr += '<FeedInfo>'
  outstr += xmlh.output_val('providerID', org_id)
  outstr += xmlh.output_val('providerName', "350org")
  outstr += xmlh.output_val('feedID', "350org")
  outstr += xmlh.output_val('createdDateTime', xmlh.current_ts())
  outstr += xmlh.output_val('providerURL', "http://www.350.org/")
  outstr += '</FeedInfo>'
  # 1 "organization" in 350.org postings
  outstr += '<Organizations><Organization>'
  outstr += xmlh.output_val('organizationID', org_id)
  outstr += '<nationalEIN></nationalEIN>'
  outstr += '<name>350.org</name>'
  outstr += xmlh.output_val('missionStatement', mission_statement)
  outstr += xmlh.output_val('description', org_desc)
  outstr += '<location>'
  outstr += xmlh.output_val("city", "")
  outstr += xmlh.output_val("region", "")
  outstr += xmlh.output_val("postalCode", "")
  outstr += '</location>'
  # TODO: make these variables
  outstr += '<organizationURL>http://www.350.org/</organizationURL>'
  outstr += '<donateURL>http://www.350.org/donate</donateURL>'
  outstr += '<logoURL>http://www.350.org/sites/all/themes/threefifty/logo.gif</logoURL>'
  outstr += '<detailURL>http://www.350.org/about</detailURL>'
  outstr += '</Organization></Organizations>'

  outstr += '\n<VolunteerOpportunities>\n'
  nodes = feed.getElementsByTagName('node')
  for i, node in enumerate(nodes):
    if maxrec > 0 and i > maxrec:
       break
    title = '<![CDATA[' + xmlh.get_tag_val(node, "title") + ']]>'
    desc = '<![CDATA[' + xmlh.get_tag_val(node, "Body") + ']]>'
    url = xmlh.get_tag_val(node, "Link")
    lat = xmlh.get_tag_val(node, "Latitude")
    lng = xmlh.get_tag_val(node, "Longitude")

    start_datetime = xmlh.get_tag_val(node, "Start_Date")
    start_time = None
    if not start_datetime:
      start_date = "2010-10-10"
    else:
      start_datetime = start_datetime.replace(" (All day)",  "T00:00:00")
      dt = start_datetime.split("T")
      start_date = dt[0][0:10]
      if len(dt) > 1:
        start_time = dt[1]

    end_datetime = xmlh.get_tag_val(node, "End_Date")
    end_time = None
    if not end_datetime:
      open_ended = True
    else:
      open_ended = False
      end_datetime = end_datetime.replace(" (All day)",  "T23:00:00")
      dt = end_datetime.split("T")
      end_date = dt[0][0:10]
      if len(dt) > 1:
        end_time = dt[1]
      
    end_datetime = xmlh.get_tag_val(node, "End_Date")
    locstr = "%s, %s %s" % (xmlh.get_tag_val(node, "City"), 
                            xmlh.get_tag_val(node, "Province"), 
                            xmlh.get_tag_val(node, "Country"))

    outstr += '<VolunteerOpportunity>'
    outstr += '<volunteerOpportunityID>%s</volunteerOpportunityID>' % (str(i))
    outstr += '<sponsoringOrganizationIDs><sponsoringOrganizationID>%s</sponsoringOrganizationID></sponsoringOrganizationIDs>' % (org_id)
    outstr += '<volunteerHubOrganizationIDs><volunteerHubOrganizationID>%s</volunteerHubOrganizationID></volunteerHubOrganizationIDs>' % (org_id)
    outstr += '<title>%s</title>' % (title)
    outstr += '<detailURL>%s</detailURL>' % (url)
    outstr += '<description>%s</description>' % (desc)
    outstr += '<abstract>%s</abstract>' % (desc)
    outstr += '<lastUpdated>%s</lastUpdated>' %(last_updated)
    outstr += '<locations><location>'
    outstr += '<location_string>%s</location_string>' % (locstr)
    outstr += '<latitude>%s</latitude>' % (lat)
    outstr += '<longitude>%s</longitude>' % (lng)
    outstr += '</location></locations>'
    outstr += '<dateTimeDurations><dateTimeDuration>'
    outstr += '<startDate>%s</startDate>' % (start_date)
    if start_time:
      outstr += '<startTime>%s</startTime>' % (start_time)
    if open_ended:
      outstr += '<openEnded>Yes</openEnded>'
    else:
      outstr += '<openEnded>No</openEnded>'
      outstr += '<endDate>%s</endDate>' % (end_date)
      if end_time:
        outstr += '<endTime>%s</endTime>' % (end_time)
    outstr += '</dateTimeDuration></dateTimeDurations>'
    outstr += '</VolunteerOpportunity>\n'
    numopps += 1
  outstr += '</VolunteerOpportunities>'
  outstr += '</FootprintFeed>'

  return outstr, numorgs, numopps
