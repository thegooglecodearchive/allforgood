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
parser for custom diy items -- not FPXML
"""

# example record
"""
sponsoringOrganization  title   description     url     Subject Area    Key Words
Corporation for National & Community Service    Creating a Service Project      Creating a service project requires a number of steps.  This Foundation segment of the MLK Day toolkits provides the steps for creating a service project in any topic area     http://mlkday.gov/plan/actionguides/foundation.php      General Service Project Service, Project, Create, MLK, Dr. King, Honor
"""
import sys
import re
import xml.sax.saxutils
import xml_helpers as xmlh
from datetime import datetime
import dateutil.parser

def get_field(field, row, header):
  for i, fname in enumerate(header):
    if fname == field:
      try:
        return row[i]
      except:
        print "bad row: (%s)" % str(row)
  return ""

# pylint: disable-msg=R0915
def parse(instr, maxrec, progress):
  """return FPXML given sparked feed data"""
  from xml.dom import minidom

  org_id = "140"
  mission_statement = "Do it yourself volunteer opportunities."
  org_desc = "Do it yourself volunteer opportunities"

  today = datetime.now()
  last_updated = today.strftime("%Y-%m-%dT%H:%M:%S")

  numorgs = 1
  numopps = 0
  xmlh.print_progress("loading diy custom TSV...")

  # convert to footprint format
  outstr = '<?xml version="1.0" ?>'
  outstr += '<FootprintFeed schemaVersion="0.1">'
  outstr += '<FeedInfo>'
  outstr += xmlh.output_val('providerID', org_id)
  outstr += xmlh.output_val('providerName', "diy")
  outstr += xmlh.output_val('feedID', "diy")
  outstr += xmlh.output_val('createdDateTime', xmlh.current_ts())
  outstr += xmlh.output_val('providerURL', "http://www.allforgood.org/")
  outstr += '</FeedInfo>'
  outstr += '<Organizations><Organization>'
  outstr += xmlh.output_val('organizationID', org_id)
  outstr += '<nationalEIN></nationalEIN>'
  outstr += '<name>allforgood.org</name>'
  outstr += xmlh.output_val('missionStatement', mission_statement)
  outstr += xmlh.output_val('description', org_desc)
  outstr += '<location>'
  outstr += xmlh.output_val("city", "San Francisco")
  outstr += xmlh.output_val("region", "CA")
  outstr += xmlh.output_val("postalCode", "94105")
  outstr += '</location>'
  outstr += '<organizationURL>http://www.allforgood.org/</organizationURL>'
  outstr += '<donateURL>http://www.allforgood.org/</donateURL>'
  outstr += '<logoURL>http://www.allforgood.org/</logoURL>'
  outstr += '<detailURL>http://www.allforgood.org/</detailURL>'
  outstr += '</Organization></Organizations>'
  outstr += '<VolunteerOpportunities>'
  
  lines = instr.split("\n")
  header = lines.pop(0).strip().split("\t")
  
  for i, line in enumerate(lines):
    row =  line.strip().split("\t")
    if maxrec > 0 and i > maxrec:
       break
    
    title = '<![CDATA[' + get_field("title", row, header) + ']]>'
    url = get_field("url", row, header)
    if not title or not url:
      continue

    sponsor = get_field("sponsoringOrganization", row, header)
    desc = ('<![CDATA[' 
         + sponsor + ': ' + get_field("description", row, header) 
         + ' Areas of interest: ' + get_field("subjectArea", row, header) 
         + ' Tags: ' + get_field("keywords", row, header) 
         + ']]>')

    start_date = last_updated
    outstr += '<VolunteerOpportunity>'
    outstr += '<volunteerOpportunityID>%s</volunteerOpportunityID>' % (str(i))
    outstr += '<sponsoringOrganizationIDs><sponsoringOrganizationID>%s</sponsoringOrganizationID></sponsoringOrganizationIDs>' % (org_id)
    outstr += '<volunteerHubOrganizationIDs><volunteerHubOrganizationID>%s</volunteerHubOrganizationID></volunteerHubOrganizationIDs>' % (org_id)
    outstr += '<self_directed>Yes</self_directed>'
    outstr += '<title>%s</title>' % (title)
    outstr += '<detailURL><![CDATA[%s]]></detailURL>' % (url)
    outstr += '<description>%s</description>' % (desc)
    outstr += '<abstract>%s</abstract>' % (desc)
    outstr += '<lastUpdated>%s</lastUpdated>' %(last_updated)
    outstr += '<dateTimeDurations><dateTimeDuration>'
    outstr += '<startDate>%s</startDate>' % (start_date)
    outstr += '<openEnded>Yes</openEnded>'
    outstr += '</dateTimeDuration></dateTimeDurations>'
    outstr += '<locations><location><virtual>Yes</virtual></location></locations>'
    outstr += '</VolunteerOpportunity>'
    numopps += 1

  outstr += '</VolunteerOpportunities>'
  outstr += '</FootprintFeed>'

  return outstr, numorgs, numopps
