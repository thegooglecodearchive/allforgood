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
parser for idealist custom feed -- not FPXML
<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:g="http://base.google.com/ns/1.0" xmlns:awb="http://base.google.com/cns/1.0">
  <title>Idealist.org - Volunteer Opportunities</title>
  <subtitle>
    Volunteer Opportunities that were posted to idealist.org in English
  </subtitle>
  <updated>2011-02-25T00:43:24Z</updated>
  <id>http://www.idealist.org/search</id>
  <link rel="self" type="application/atom+xml" href="http://www.idealist.org/search?search_type=volop&amp;search_language=en"/>
  <icon>http://www.idealist.org/facvicon.ico</icon>
  <logo>http://www.idealist.org/images/wrapper/idealistLogo-en.gif</logo>
  <author>
    <name>Action Without Borders - idealist.org</name>
    <uri>http://www.idealist.org/</uri>
    <email>feeds@idealist.org</email>
  </author>
  <rights>1995-2010, Action Without Borders</rights>
  <entry xmlns="http://www.w3.org/2005/Atom">
    <title>Regional Director - San Jose</title>
    <link rel="alternate" type="text/html" hreflang="en" href="http://www.idealist.org/view/volop/pStJKz83W9h4/"/>
    <id>http://www.idealist.org/view/volop/pStJKz83W9h4/</id>
    <published>2011-02-23T21:59:44Z</published>
    <g:publish_date>2011-02-23</g:publish_date>
    <updated>2011-02-23T21:59:44Z</updated>
    <category term="Politics" label="Politics" scheme="http://www.idealist.org/atom/namespace/aof-Org"/><category term="International relations" label="International relations" scheme="http://www.idealist.org/atom/namespace/aof-Org"/><category term="Poverty and hunger" label="Poverty and hunger" scheme="http://www.idealist.org/atom/namespace/aof-Org"/>
    <summary>http://www.borgenproject.org/
THE BORGEN PROJECT
The Borgen Project believes that leaders of the most powerful nation on earth should be doing more to address global poverty. We're the innovative, national campaign that is working to make poverty a focus </summary>
    <content type="html">...</content>
        <awb:city type="string">New York</awb:city>
        <awb:state type="string">US_NY</awb:state>
        <awb:postal_code type="string">10007</awb:postal_code>
        <awb:country type="string">US</awb:country>
        <g:location>1 Centre St., New York, NY, 10007, US</g:location>
    <awb:posted_by type="string">Big Apple Greeter</awb:posted_by>
    <awb:poster_ein type="string">13-3733413</awb:poster_ein>
  <g:id>dD4Bmh2jKCcp</g:id>
      <g:employer>Big Apple Greeter</g:employer>
      <g:job_function>Volunteer Greeter</g:job_function>
      <g:job_type>Volunteer</g:job_type>
      <g:job_industry>Nonprofit</g:job_industry>
  </entry>
</feed>
"""
import sys
import re
import xml.sax.saxutils
import xml_helpers as xmlh
from datetime import datetime
import dateutil.parser

from xml.dom import minidom

# pylint: disable-msg=R0915
def parse(instr, maxrec, progress):
  """return FPXML given idealist feed data"""
  #feed = xmlh.parse_or_die(instr.encode('utf-8'))
  instr = instr.encode('utf-8')
  try:
    feed = minidom.parseString(instr)
  except xml.parsers.expat.ExpatError, err:
    feed = None
    print datetime.now(), "XML parsing error on line ", err.lineno,
    print ":", xml.parsers.expat.ErrorString(err.code),
    print " (column ", err.offset, ")"
    lines = instr.split("\n")
    for i in range(err.lineno - 3, err.lineno + 3):
      if i >= 0 and i < len(lines):
        print "%6d %s" % (i+1, lines[i])

  if not feed:
    print "trying CDATA content..."
    instr = instr.replace('<content type="html">', 
                          '<content type="html"><![CDATA[').replace('</content>', 
                                                                    ']]></content>')
    try:
      feed = minidom.parseString(instr)
    except:
      pass

  if not feed:
    return '', 0, 0

  org_id = str(103)
  mission_statement = "Idealist connects people, organizations, and resources to help build a world where all people can live free and dignified lives.  Idealist is independent of any government, political ideology, or religious creed. Our work is guided by the common desire of our members and supporters to find practical solutions to social and environmental problems, in a spirit of generosity and mutual respect."

  org_desc = "Volunteer Opportunities that were posted to idealist.org in English"

  today = datetime.now()
  last_updated = today.strftime("%Y-%m-%dT%H:%M:%S")
  start_date = last_updated

  numorgs = 1
  numopps = 0
  xmlh.print_progress("loading idealist.xml custom XML...")

  # convert to footprint format
  outstr = '<?xml version="1.0" ?>'
  outstr += '<FootprintFeed schemaVersion="0.1">'
  outstr += '<FeedInfo>'
  outstr += xmlh.output_val('providerID', org_id)
  outstr += xmlh.output_val('providerName', "idealist")
  outstr += xmlh.output_val('feedID', "idealist")
  outstr += xmlh.output_val('createdDateTime', xmlh.current_ts())
  outstr += xmlh.output_val('providerURL', "http://www.idealist.org/")
  outstr += '</FeedInfo>'
  # 1 "organization" in idealist.org postings
  outstr += '<Organizations><Organization>'
  outstr += xmlh.output_val('organizationID', org_id)
  outstr += '<nationalEIN></nationalEIN>'
  outstr += '<name>idealist.org</name>'
  outstr += xmlh.output_val('missionStatement', mission_statement)
  outstr += xmlh.output_val('description', org_desc)
  outstr += '<location>'
  outstr += xmlh.output_val("city", "New York")
  outstr += xmlh.output_val("region", "NY")
  outstr += xmlh.output_val("postalCode", "10001")
  outstr += '</location>'
  outstr += '<organizationURL>http://www.idealist.org/</organizationURL>'
  outstr += '<donateURL>http://www.idealist.org/</donateURL>'
  outstr += '<logoURL>http://www.idealist.org/css/skin02/images/logoBG.png</logoURL>'
  outstr += '<detailURL>http://www.idealist.org/</detailURL>'
  outstr += '</Organization></Organizations>'

  outstr += '\n<VolunteerOpportunities>\n'
  try:
    nodes = feed.getElementsByTagName('entry')
  except:
    nodes = []
    
  for i, node in enumerate(nodes):
    if maxrec > 0 and i > maxrec:
       break
    title = '<![CDATA[' + xmlh.get_tag_val(node, "title") + ']]>'
    desc = '<![CDATA[' + xmlh.get_tag_val(node, "summary") + ']]>'
    url = xmlh.get_tag_val(node, "id")

    start_date = last_updated
    open_ended = True
    outstr += '<VolunteerOpportunity>'
    outstr += '<volunteerOpportunityID>%s</volunteerOpportunityID>' % (str(i))
    outstr += '<sponsoringOrganizationIDs><sponsoringOrganizationID>'
    outstr += org_id
    outstr += '</sponsoringOrganizationID></sponsoringOrganizationIDs>'
    outstr += '<volunteerHubOrganizationIDs><volunteerHubOrganizationID>'
    outstr += org_id 
    outstr += '</volunteerHubOrganizationID></volunteerHubOrganizationIDs>'
    outstr += '<title>%s</title>' % (title)
    outstr += '<detailURL>%s</detailURL>' % (url)
    outstr += '<description>%s</description>' % (desc)
    outstr += '<abstract>%s</abstract>' % (desc)
    outstr += '<lastUpdated>%s</lastUpdated>' %(last_updated)
    outstr += '<dateTimeDurations><dateTimeDuration>'
    outstr += '<startDate>%s</startDate>' % (start_date)
    outstr += '<openEnded>Yes</openEnded>'
    outstr += '</dateTimeDuration></dateTimeDurations>'
    outstr += '<locations><location>'
    outstr += '<virtual>no</virtual>'
    outstr += '<streetAddress1><![CDATA[' +xmlh.get_tag_val(node, "g:location") + ']]></streetAddress1>'
    outstr += '<city><![CDATA[' + xmlh.get_tag_val(node, "awb:city") + ']]></city>'
    outstr += '<region><![CDATA[' + xmlh.get_tag_val(node, "awb:state") + ']]></region>'
    outstr += '<postalCode><![CDATA[' + xmlh.get_tag_val(node, "awb:postal_code") + ']]></postalCode>'
    outstr += '</location></locations>'
    outstr += '</VolunteerOpportunity>\n'
    numopps += 1
  outstr += '</VolunteerOpportunities>'
  outstr += '</FootprintFeed>'

  return outstr, numorgs, numopps
