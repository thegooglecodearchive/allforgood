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
parser for volunteermatch
"""
import xml_helpers as xmlh
from datetime import datetime

import dateutil.parser

# pylint: disable-msg=R0915
def parse(s, maxrecs, progress):
  """return FPXML given volunteermatch data"""
  # TODO: progress
  known_elnames = ['feed', 'title', 'subtitle', 'div', 'span', 'updated', 'id', 'link', 'icon', 'logo', 'author', 'name', 'uri', 'email', 'rights', 'entry', 'published', 'g:publish_date', 'g:expiration_date', 'g:event_date_range', 'g:start', 'g:end', 'updated', 'category', 'summary', 'content', 'awb:city', 'awb:country', 'awb:state', 'awb:postalcode', 'g:location', 'g:age_range', 'g:employer', 'g:job_type', 'g:job_industry', 'awb:paid', ]
  xmldoc = xmlh.simple_parser(s, known_elnames, progress)

  pubdate = xmlh.get_tag_val(xmldoc, "created")
  ts = dateutil.parser.parse(pubdate)
  pubdate = ts.strftime("%Y-%m-%dT%H:%M:%S")

  # convert to footprint format
  s = '<?xml version="1.0" ?>'
  s += '<FootprintFeed schemaVersion="0.1">'
  s += '<FeedInfo>'
  # TODO: assign provider IDs?
  s += '<providerID>104</providerID>'
  s += '<providerName>volunteermatch.org</providerName>'
  s += '<feedID>1</feedID>'
  s += '<providerURL>http://www.volunteermatch.org/</providerURL>'
  s += '<createdDateTime>%s</createdDateTime>' % (pubdate)
  s += '<description></description>' 
  s += '</FeedInfo>'

  numorgs = numopps = 0

  # hardcoded: Organization
  s += '<Organizations>'
  items = xmldoc.getElementsByTagName("listing")
  if (maxrecs > items.length or maxrecs == -1):
    maxrecs = items.length
    
  for item in items[0:maxrecs]:
    orgs = item.getElementsByTagName("parent")
    if (orgs.length == 1):
      org = orgs[0]
      s += '<Organization>'
      s += '<organizationID>%s</organizationID>' % (xmlh.get_tag_val(org, "key"))
      s += '<nationalEIN></nationalEIN>'
      s += '<name>%s</name>' % (xmlh.get_tag_val(org, "name"))
      s += '<missionStatement></missionStatement>'
      s += '<description></description>'
      s += '<location><city></city><region></region><postalCode></postalCode></location>'
      s += '<organizationURL>%s</organizationURL>' % (xmlh.get_tag_val(org, "URL"))
      s += '<donateURL></donateURL>'
      s += '<logoURL></logoURL>'
      s += '<detailURL>%s</detailURL>' % (xmlh.get_tag_val(org, "detailURL"))
      s += '</Organization>'
      numorgs += 1
    else:
      print datetime.now(), "parse_volunteermatch: listing does not have an organization"
      return None

  s += '</Organizations>'
    
  s += '<VolunteerOpportunities>'
  items = xmldoc.getElementsByTagName("listing")
  for item in items[0:maxrecs]:
    s += '<VolunteerOpportunity>'
    s += '<volunteerOpportunityID>%s</volunteerOpportunityID>' % (xmlh.get_tag_val(item, "key"))

    orgs = item.getElementsByTagName("parent")
    if (orgs.length == 1):
      org = orgs[0]
      s += '<sponsoringOrganizationIDs><sponsoringOrganizationID>%s</sponsoringOrganizationID></sponsoringOrganizationIDs>' % (xmlh.get_tag_val(org, "key"))
    else:
      s += '<sponsoringOrganizationIDs><sponsoringOrganizationID>0</sponsoringOrganizationID></sponsoringOrganizationIDs>'
      print datetime.now(), "parse_volunteermatch: listing does not have an organization"
      
    s += '<title>%s</title>' % (xmlh.get_tag_val(item, "title"))

    s += '<volunteersNeeded>-8888</volunteersNeeded>'

    s += '<dateTimeDurations><dateTimeDuration>'
    durations = xmlh.get_children_by_tagname(item, "duration")
    if (len(durations) == 1):
      duration = durations[0]
      ongoing = duration.getAttribute("ongoing")
      if (ongoing == 'true'):
        s += '<openEnded>Yes</openEnded>'
      else:
        s += '<openEnded>No</openEnded>'
          
      listingTimes = duration.getElementsByTagName("listingTime")
      if (listingTimes.length == 1):
        listingTime = listingTimes[0]
        s += '<startTime>%s</startTime>' % (xmlh.get_tag_val(listingTime, "startTime"))
        s += '<endTime>%s</endTime>' % (xmlh.get_tag_val(listingTime, "endTime"))
    else:
      print datetime.now(), "parse_volunteermatch: number of durations in item != 1"
      return None
        
    commitments = item.getElementsByTagName("commitment")
    l_period = l_duration = ""
    if (commitments.length == 1):
      commitment = commitments[0]
      l_num = xmlh.get_tag_val(commitment, "num")
      l_duration = xmlh.get_tag_val(commitment, "duration")
      l_period = xmlh.get_tag_val(commitment, "period")
      if ((l_duration == "hours") and (l_period == "week")):
        s += '<commitmentHoursPerWeek>' + l_num + '</commitmentHoursPerWeek>'
      elif ((l_duration == "hours") and (l_period == "day")):
        # note: weekdays only
        s += '<commitmentHoursPerWeek>' + str(int(l_num)*5) + '</commitmentHoursPerWeek>'
      elif ((l_duration == "hours") and (l_period == "month")):
        hrs = int(float(l_num)/4.0)
        if hrs < 1: hrs = 1
        s += '<commitmentHoursPerWeek>' + str(hrs) + '</commitmentHoursPerWeek>'
      elif ((l_duration == "hours") and (l_period == "event")):
        # TODO: ignore for now, later compute the endTime if not already provided
        pass
      else:
        print datetime.now(), "parse_volunteermatch: commitment given in units != hours/week: ", l_duration, "per", l_period
        
    s += '</dateTimeDuration></dateTimeDurations>'

    dbaddresses = item.getElementsByTagName("location")
    if (dbaddresses.length != 1):
      print datetime.now(), "parse_volunteermatch: only 1 location supported."
      return None
    dbaddress = dbaddresses[0]
    s += '<locations><location>'
    s += '<streetAddress1>%s</streetAddress1>' % (xmlh.get_tag_val(dbaddress, "street1"))
    s += '<city>%s</city>' % (xmlh.get_tag_val(dbaddress, "city"))
    s += '<region>%s</region>' % (xmlh.get_tag_val(dbaddress, "region"))
    s += '<postalCode>%s</postalCode>' % (xmlh.get_tag_val(dbaddress, "postalCode"))
    
    geolocs = item.getElementsByTagName("geolocation")
    if (geolocs.length == 1):
      geoloc = geolocs[0]
      s += '<latitude>%s</latitude>' % (xmlh.get_tag_val(geoloc, "latitude"))
      s += '<longitude>%s</longitude>' % (xmlh.get_tag_val(geoloc, "longitude"))
    
    s += '</location></locations>'
    
    s += '<audienceTags>'
    audiences = item.getElementsByTagName("audience")
    for audience in audiences:
      type = xmlh.node_data(audience)
      s += '<audienceTag>%s</audienceTag>' % (type)
    s += '</audienceTags>'

    s += '<categoryTags>'
    categories = item.getElementsByTagName("category")
    for category in categories:
      type = xmlh.node_data(category)
      s += '<categoryTag>%s</categoryTag>' % (type)
    s += '</categoryTags>'

    s += '<skills>%s</skills>' % (xmlh.get_tag_val(item, "skill"))

    s += '<detailURL>%s</detailURL>' % (xmlh.get_tag_val(item, "detailURL"))
    s += '<description>%s</description>' % (xmlh.get_tag_val(item, "description"))

    expires = xmlh.get_tag_val(item, "expires")
    ts = dateutil.parser.parse(expires)
    expires = ts.strftime("%Y-%m-%dT%H:%M:%S")
    s += '<expires>%s</expires>' % (expires)

    s += '</VolunteerOpportunity>'
    numopps += 1
    
  s += '</VolunteerOpportunities>'
  s += '</FootprintFeed>'

  #s = re.sub(r'><([^/])', r'>\n<\1', s)
  #print(s)
  return s, numorgs, numopps
