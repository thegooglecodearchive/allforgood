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
parser for sparked.com custom feed -- not FPXML
"""

# example record
"""
<challenges>
<challenge>
<title>How we can optimize our website for online giving?</title>
<url>
http://sparked.com/ask/How-we-can-optimize-our-website-for-online-giving-28
</url>
<description>
We'd love some feedback about how to make our website more online giving friendly... 
</description>
<cause>environment</cause>
<skill>fundraising</skill>
<deadline>02/15/11</deadline>
<daysLeft>1 day left</daysLeft>
<numAnswers>7</numAnswers>
<numSolvers>5</numSolvers>
<seeker>
<firstName>Steve</firstName>
<lastName>R.</lastName>
<sparkedProfileUrl>http://sparked.com/profile/be300bb6da</sparkedProfileUrl>
<orgName>Kids4Trees</orgName>
<orgBio>
Our mission is ...
</orgBio>
<orgUrl>http://www.kids4trees.org</orgUrl>
<orgAccreditation>Fiscally Sponsored Nonprofit</orgAccreditation>
</seeker>
<solvers/>
</challenge>
"""
import sys
import re
import xml.sax.saxutils
import xml_helpers as xmlh
from datetime import datetime
import dateutil.parser

# pylint: disable-msg=R0915
def parse(instr, maxrec, progress):
  """return FPXML given sparked feed data"""
  from xml.dom import minidom
  feed = minidom.parseString(instr.encode('utf-8'))
  """
  try:
    feed = minidom.parseString(instr.encode('utf-8'))
  except:
    return None, 0, 0
  """

  org_id = str(139)
  mission_statement = "Sparked makes it easy for people with busy lives to help nonprofits get valuable work done when it's convenient. We call it microvolunteering. Through the convenience of the Internet, and with the collaboration of others, micro-volunteers use their professional skills to help causes they care about."
  org_desc = "Sparked is the world's first Microvolunteering network"

  today = datetime.now()
  last_updated = today.strftime("%Y-%m-%dT%H:%M:%S")
  start_date = last_updated

  numorgs = 1
  numopps = 0
  xmlh.print_progress("loading sparked.com custom XML...")

  # convert to footprint format
  outstr = '<?xml version="1.0" ?>'
  outstr += '<FootprintFeed schemaVersion="0.1">'
  outstr += '<FeedInfo>'
  outstr += xmlh.output_val('providerID', org_id)
  outstr += xmlh.output_val('providerName', "sparked")
  outstr += xmlh.output_val('feedID', "sparked")
  outstr += xmlh.output_val('createdDateTime', xmlh.current_ts())
  outstr += xmlh.output_val('providerURL', "http://www.sparked.com/")
  outstr += '</FeedInfo>'
  # 1 "organization" in sparked.com postings
  outstr += '<Organizations><Organization>'
  outstr += xmlh.output_val('organizationID', org_id)
  outstr += '<nationalEIN></nationalEIN>'
  outstr += '<name>sparked.com</name>'
  outstr += xmlh.output_val('missionStatement', mission_statement)
  outstr += xmlh.output_val('description', org_desc)
  outstr += '<location>'
  outstr += xmlh.output_val("city", "San Francisco")
  outstr += xmlh.output_val("region", "CA")
  outstr += xmlh.output_val("postalCode", "94105")
  outstr += '</location>'
  outstr += '<organizationURL>http://www.sparked.com/</organizationURL>'
  outstr += '<donateURL>http://www.sparked.com/</donateURL>'
  outstr += '<logoURL>http://www.sparked.com/imgver4/logo_sparked.gif</logoURL>'
  outstr += '<detailURL>http://www.sparked.com/</detailURL>'
  outstr += '</Organization></Organizations>'

  outstr += '\n<VolunteerOpportunities>\n'
  nodes = feed.getElementsByTagName('challenge')
  for i, node in enumerate(nodes):
    if maxrec > 0 and i > maxrec:
       break
    title = '<![CDATA[' + xmlh.get_tag_val(node, "title") + ']]>'
    desc = '<![CDATA[' + xmlh.get_tag_val(node, "description") + ']]>'
    url = xmlh.get_tag_val(node, "url")

    start_date = last_updated
    open_ended = True
    #01234567
    #02/15/11
    mdy = xmlh.get_tag_val(node, "deadline")
    if mdy:
      try:
        end_date = str(2000 + int(mdy[6:])) + "-" + mdy[0:2] + "-" + mdy[3:2]
        open_ended = False
      except:
        pass
    outstr += '<VolunteerOpportunity>'
    outstr += '<volunteerOpportunityID>%s</volunteerOpportunityID>' % (str(i))
    outstr += '<sponsoringOrganizationIDs><sponsoringOrganizationID>%s</sponsoringOrganizationID></sponsoringOrganizationIDs>' % (org_id)
    outstr += '<volunteerHubOrganizationIDs><volunteerHubOrganizationID>%s</volunteerHubOrganizationID></volunteerHubOrganizationIDs>' % (org_id)
    outstr += '<micro>Yes</micro>'
    outstr += '<title>%s</title>' % (title)
    outstr += '<detailURL>%s</detailURL>' % (url)
    outstr += '<description>%s</description>' % (desc)
    outstr += '<abstract>%s</abstract>' % (desc)
    outstr += '<lastUpdated>%s</lastUpdated>' %(last_updated)
    outstr += '<dateTimeDurations><dateTimeDuration>'
    outstr += '<startDate>%s</startDate>' % (start_date)
    if open_ended:
      outstr += '<openEnded>Yes</openEnded>'
    else:
      outstr += '<openEnded>No</openEnded>'
      outstr += '<endDate>%s</endDate>' % (end_date)
    outstr += '</dateTimeDuration></dateTimeDurations>'
    outstr += '<locations><location><virtual>Yes</virtual></location></locations>'
    outstr += '</VolunteerOpportunity>\n'
    numopps += 1
  outstr += '</VolunteerOpportunities>'
  outstr += '</FootprintFeed>'

  return outstr, numorgs, numopps
