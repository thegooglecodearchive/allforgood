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
parser for Network For Good feeds
"""

import xml_helpers as xmlh
import xml.sax.saxutils
import re
from datetime import datetime

ORGS = {}
ORGIDS = {}
MAX_ORGID = 0

def register_org(item):
  """register the organization info, for lookup later."""
  global MAX_ORGID

  # SponsoringOrganization/Name -- fortunately, no conflicts
  # but there's no data except the name
  orgname = xmlh.get_tag_val(item, "Name")
  if orgname in ORGIDS:
    return ORGIDS[orgname]
  MAX_ORGID = MAX_ORGID + 1
  orgstr = '<Organization>'
  orgstr += '<organizationID>%d</organizationID>' % (MAX_ORGID)
  orgstr += '<nationalEIN />'
  orgstr += '<name>%s</name>' % (xml.sax.saxutils.escape(orgname))
  orgstr += '<missionStatement />'
  orgstr += '<description />'
  orgstr += '<location>'
  orgstr += xmlh.output_node("city", item, "City")
  orgstr += xmlh.output_node("region", item, "StateOrProvince")
  orgstr += xmlh.output_node("postalCode", item, "ZipOrPostalCode")
  orgstr += '</location>'
  orgstr += '<organizationURL />'
  orgstr += '<donateURL />'
  orgstr += '<logoURL />'
  orgstr += '<detailURL />'
  orgstr += '</Organization>'
  ORGS[MAX_ORGID] = orgstr
  ORGIDS[orgname] = MAX_ORGID
  return MAX_ORGID

# pylint: disable-msg=R0915
def parser(providerID, providerName, feedID, providerURL, feedDescription):
  """create an NFG-compatible parser"""

  known_elnames = [
    'Abstract', 'Categories', 'Category', 'CategoryID', 'Country', 'DateListed',
    'Description', 'DetailURL', 'Duration', 'DurationQuantity', 'DurationUnit',
    'EndDate', 'KeyWords', 'LocalID', 'Location', 'LocationClassification',
    'LocationClassificationID', 'LocationClassifications', 'Locations',
    'LogoURL', 'Name', 'OpportunityDate', 'OpportunityDates', 'OpportunityType',
    'OpportunityTypeID', 'SponsoringOrganization', 'SponsoringOrganizations',
    'StartDate', 'StateOrProvince', 'Title', 'VolunteerOpportunity',
    'ZipOrPostalCode' ]

  def parse(instr, maxrecs, progress):
    numorgs = numopps = 0
    instr = re.sub(r'<(/?db):', r'<\1_', instr)
    opps = re.findall(r'<VolunteerOpportunity>.+?</VolunteerOpportunity>',
                      instr, re.DOTALL)
    volopps = ""
    for i, oppstr in enumerate(opps):
      if progress and i > 0 and i % 250 == 0:
        print str(datetime.now())+": ", i, " opportunities processed."
      if (maxrecs > 0 and i > maxrecs):
        break
      xmlh.print_rps_progress("opps", progress, i, maxrecs)
  
      item = xmlh.simple_parser(oppstr, known_elnames, progress=False)
  
      orgid = register_org(item)
  
      # logoURL -- sigh, this is for the opportunity not the org
      volopps += '<VolunteerOpportunity>'
      volopps += xmlh.output_val('volunteerOpportunityID', str(i))
      volopps += xmlh.output_val('sponsoringOrganizationID', str(orgid))
      volopps += xmlh.output_node('volunteerHubOrganizationID', item, "LocalID")
      volopps += xmlh.output_node('title', item, "Title")
      volopps += xmlh.output_node('abstract', item, "Description")
      volopps += xmlh.output_node('description', item, "Description")
      volopps += xmlh.output_node('detailURL', item, "DetailURL")
      volopps += xmlh.output_val('volunteersNeeded', "-8888")
  
      try:
        oppdates = item.getElementsByTagName("OpportunityDate")
      except:
        oppdates = []
      
      if oppdates.length > 1:
        print datetime.now(), \
            "parse_servenet.py: only 1 OpportunityDate supported."
        #return None
        oppdate = oppdates[0]
      elif oppdates.length == 0:
        oppdate = None
      else:
        oppdate = oppdates[0]
      volopps += '<dateTimeDurations><dateTimeDuration>'
  
      if oppdate:
        volopps += xmlh.output_val('openEnded', 'No')
        volopps += xmlh.output_val('duration', 'P%s%s' % 
                                  (xmlh.get_tag_val(oppdate, "DurationQuantity"),
                                   xmlh.get_tag_val(oppdate, "DurationUnit")))
        volopps += xmlh.output_val('commitmentHoursPerWeek', '0')
        volopps += xmlh.output_node('startDate', oppdate, "StartDate")
        volopps += xmlh.output_node('endDate', oppdate, "EndDate")
      else:
        volopps += xmlh.output_val('openEnded', 'Yes')
        volopps += xmlh.output_val('commitmentHoursPerWeek', '0')
      volopps += '</dateTimeDuration></dateTimeDurations>'
  
      volopps += '<locations>'
      try:
        opplocs = item.getElementsByTagName("Location")
      except:
        opplocs = []
      for opploc in opplocs:
        volopps += '<location>'
        virtual_tag = opploc.getElementsByTagName("Virtual")
        if virtual_tag and xmlh.get_tag_val(opploc, "Virtual").lower() == "yes":
          volopps += xmlh.output_val('virtual', 'Yes')
        else:
          volopps += xmlh.output_node('region', opploc, "StateOrProvince")
          volopps += xmlh.output_node('country', opploc, "Country")
          volopps += xmlh.output_node('postalCode', opploc, "ZipOrPostalCode")
        volopps += '</location>'
      volopps += '</locations>'
      volopps += '<categoryTags/>'
      volopps += '</VolunteerOpportunity>'
      numopps += 1
      
    # convert to footprint format
    outstr = '<?xml version="1.0" ?>'
    outstr += '<FootprintFeed schemaVersion="0.1">'
    outstr += '<FeedInfo>'
    outstr += xmlh.output_val('providerID', providerID)
    outstr += xmlh.output_val('providerName', providerName)
    outstr += xmlh.output_val('feedID', feedID)
    outstr += xmlh.output_val('createdDateTime', xmlh.current_ts())
    outstr += xmlh.output_val('providerURL', providerURL)
    outstr += xmlh.output_val('description', feedDescription)
    # TODO: capture ts -- use now?!
    outstr += '</FeedInfo>'
  
    # hardcoded: Organization
    outstr += '<Organizations>'
    for key in ORGS:
      outstr += ORGS[key]
      numorgs += 1
    outstr += '</Organizations>'
    outstr += '<VolunteerOpportunities>'
    outstr += volopps
    outstr += '</VolunteerOpportunities>'
    outstr += '</FootprintFeed>'
  
    #outstr = re.sub(r'><([^/])', r'>\n<\1', outstr)
    return outstr, numorgs, numopps

  return parse
