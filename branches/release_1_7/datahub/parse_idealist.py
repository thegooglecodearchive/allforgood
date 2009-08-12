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
parser for idealist, which (IIRC) originates from Base?
"""
import xml_helpers as xmlh
import re
from datetime import datetime
import xml.sax.saxutils

import dateutil.parser

# xml parser chokes on namespaces, and since we don't need them,
# just replace them for simplicity-- note that this also affects
# the code below
def remove_g_namespace(s, progress):
  if progress:
    print datetime.now(), "removing g: namespace..."
  s = re.sub(r'<(/?)g:', r'<\1gg_', s)
  if progress:
    print datetime.now(), "removing awb: namespace..."
  s = re.sub(r'<(/?)awb:', r'<\1awb_', s)
  return s

def addCdataToContent(s, progress):
  # what if CDATA is already used?!
  if progress:
    print datetime.now(), "adding CDATA to <content>..."
  ## yuck: this caused a RAM explosion...
  #rx = re.compile(r'<content( *?[^>]*?)>(.+?)</content>', re.DOTALL)
  #s = re.sub(rx, r'<content\1><![CDATA[\2]]></content>', s)

  s = re.sub(r'<content([^>]+)>', r'<content\1><![CDATA[', s)
  if progress:
    print datetime.now(), "adding ]]> to </content>..."
  s = re.sub(r'</content>', r']]></content>', s)
  if progress:
    print datetime.now(), "done: ", len(s), " bytes"
  return s

def removeContentWrapperDiv(s):
  return re.sub(r'(.*?&lt;div.*?&gt;|&lt;/div&gt;)', '', s).strip()

# frees memory for main parse
def ParseHelper(instr, maxrecs, progress):
  # TODO: progress
  known_elnames = ['feed', 'title', 'subtitle', 'div', 'span', 'updated', 'id', 'link', 'icon', 'logo', 'author', 'name', 'uri', 'email', 'rights', 'entry', 'published', 'gg_publish_date', 'gg_expiration_date', 'gg_event_date_range', 'gg_start', 'gg_end', 'updated', 'category', 'summary', 'content', 'awb_city', 'awb_country', 'awb_state', 'awb_postalcode', 'gg_location', 'gg_age_range', 'gg_employer', 'gg_job_type', 'gg_job_industry', 'awb_paid', ]
  # takes forever
  #xmldoc = xmlh.simple_parser(s, known_elnames, progress)

  # convert to footprint format
  s = '<?xml version="1.0" ?>'
  s += '<FootprintFeed schemaVersion="0.1">'
  s += '<FeedInfo>'
  # TODO: assign provider IDs?
  s += '<feedID>1</feedID>'
  s += '<providerID>103</providerID>'
  s += '<providerName>idealist.org</providerName>'
  s += '<providerURL>http://www.idealist.org/</providerURL>'
  match = re.search(r'<title>(.+?)</title>', instr, re.DOTALL)
  if match:
    s += '<description>%s</description>' % (match.group(1))
  s += '<createdDateTime>%s</createdDateTime>' % xmlh.current_ts()
  s += '</FeedInfo>'

  numorgs = numopps = 0

  # hardcoded: Organization
  s += '<Organizations>'
  #authors = xmldoc.getElementsByTagName("author")
  organizations = {}
  authors = re.findall(r'<author>.+?</author>', instr, re.DOTALL)
  for i, orgstr in enumerate(authors):
    if progress and i > 0 and i % 250 == 0:
      print datetime.now(), ": ", i, " orgs processed."
    org = xmlh.simple_parser(orgstr, known_elnames, False)
    s += '<Organization>'
    s += '<organizationID>%d</organizationID>' % (i+1)
    s += '<nationalEIN></nationalEIN>'
    s += '<guidestarID></guidestarID>'
    name = xmlh.get_tag_val(org, "name")
    organizations[name] = i+1
    s += '<name>%s</name>' % (organizations[name])
    s += '<missionStatement></missionStatement>'
    s += '<description></description>'
    s += '<location><city></city><region></region><postalCode></postalCode></location>'
    s += '<organizationURL>%s</organizationURL>' % (xmlh.get_tag_val(org, "uri"))
    s += '<donateURL></donateURL>'
    s += '<logoURL></logoURL>'
    s += '<detailURL></detailURL>'
    s += '</Organization>'
    numorgs += 1
  s += '</Organizations>'
    
  s += '<VolunteerOpportunities>'
  entries = re.findall(r'<entry>.+?</entry>', instr, re.DOTALL)
  #entries = xmldoc.getElementsByTagName("entry")
  #if (maxrecs > entries.length):
  #  maxrecs = entries.length
  #for opp in entries[0:maxrecs-1]:
  for i, oppstr in enumerate(entries):
    if (maxrecs>0 and i>maxrecs):
      break
    xmlh.print_rps_progress("opps", progress, i, maxrecs)
    opp = xmlh.simple_parser(oppstr, known_elnames, False)
    # unmapped: db:rsvp  (seems to be same as link, but with #rsvp at end of url?)
    # unmapped: db:host  (no equivalent?)
    # unmapped: db:county  (seems to be empty)
    # unmapped: attendee_count
    # unmapped: guest_total
    # unmapped: db:title   (dup of title, above)
    # unmapped: contactName
    s += '<VolunteerOpportunity>'
    id_link = xmlh.get_tag_val(opp, "id")
    s += '<volunteerOpportunityID>%s</volunteerOpportunityID>' % (id_link)
    orgname = xmlh.get_tag_val(org, "name")  # ok to be lazy-- no other 'name's in this feed
    s += '<sponsoringOrganizationIDs><sponsoringOrganizationID>%s</sponsoringOrganizationID></sponsoringOrganizationIDs>' % (organizations[orgname])
    # hardcoded: volunteerHubOrganizationID
    s += '<volunteerHubOrganizationIDs><volunteerHubOrganizationID>0</volunteerHubOrganizationID></volunteerHubOrganizationIDs>'
    s += '<title>%s</title>' % (xmlh.get_tag_val(opp, "title"))
    # lazy: id is the same as the link field...
    s += '<detailURL>%s</detailURL>' % (id_link)
    # lazy: idealist stuffs a div in the content...
    entry_content = xmlh.get_tag_val(opp, 'content')
    s += '<description>%s</description>' % removeContentWrapperDiv(entry_content)
    s += '<abstract>%s</abstract>' % (xmlh.get_tag_val(opp, "summary"))
    pubdate = xmlh.get_tag_val(opp, "published")
    ts = dateutil.parser.parse(pubdate)
    pubdate = ts.strftime("%Y-%m-%dT%H:%M:%S")
    s += '<lastUpdated>%s</lastUpdated>' % (pubdate)
    s += '<expires>%sT23:59:59</expires>' % (xmlh.get_tag_val(opp, "gg_expiration_date"))
    dbevents = opp.getElementsByTagName("gg_event_date_range")
    if (dbevents.length != 1):
      print datetime.now(), "parse_idealist: only 1 db:event supported."
      return None
    s += '<locations><location>'
    # yucko: idealist is stored in Google Base, which only has 'location'
    # so we stuff it into the city field, knowing that it'll just get
    # concatenated down the line...
    s += '<city>%s</city>' % (xmlh.get_tag_val(opp, "gg_location"))
    s += '</location></locations>'
    dbscheduledTimes = opp.getElementsByTagName("gg_event_date_range")
    if (dbscheduledTimes.length != 1):
      print datetime.now(), "parse_usaservice: only 1 gg_event_date_range supported."
      return None
    dbscheduledTime = dbscheduledTimes[0]
    s += '<dateTimeDurations><dateTimeDuration>'
    s += '<openEnded>No</openEnded>'
    # ignore duration
    # ignore commitmentHoursPerWeek
    tempdate = xmlh.get_tag_val(dbscheduledTime, "gg_start")
    ts = dateutil.parser.parse(tempdate)
    tempdate = ts.strftime("%Y-%m-%d")
    s += '<startDate>%s</startDate>' % (tempdate)
    tempdate = xmlh.get_tag_val(dbscheduledTime, "gg_end")
    ts = dateutil.parser.parse(tempdate)
    tempdate = ts.strftime("%Y-%m-%d")
    s += '<endDate>%s</endDate>' % (tempdate)
    # TODO: timezone???
    s += '</dateTimeDuration></dateTimeDurations>'
    s += '<categoryTags>'
    # proper way is too slow...
    #cats = opp.getElementsByTagName("category")
    #for i,cat in enumerate(cats):
    #  s += '<categoryTag>%s</categoryTag>' % (cat.attributes["label"].value)
    catstrs = re.findall(r'<category term=(["][^"]+["])', oppstr, re.DOTALL)
    for cat in catstrs:
      s += "<categoryTag>" + xml.sax.saxutils.escape(cat) + "</categoryTag>"
    s += '</categoryTags>'
    age_range = xmlh.get_tag_val(opp, "gg_age_range")
    if re.match(r'and under|Families', age_range):
      s += '<minimumAge>0</minimumAge>'
    elif re.match(r'Teens', age_range):
      s += '<minimumAge>13</minimumAge>'
    elif re.match(r'Adults', age_range):
      s += '<minimumAge>18</minimumAge>'
    elif re.match(r'Seniors', age_range):
      s += '<minimumAge>65</minimumAge>'
    s += '</VolunteerOpportunity>'
    numopps += 1
  s += '</VolunteerOpportunities>'
  s += '</FootprintFeed>'

  #s = re.sub(r'><([^/])', r'>\n<\1', s)
  #print s
  return s, numorgs, numopps

# pylint: disable-msg=R0915
def parse(s, maxrecs, progress):
  """return FPXML given idealist data"""
  s = addCdataToContent(s, progress)
  s = remove_g_namespace(s, progress)
  s = ParseHelper(s, maxrecs, progress)
  return s

