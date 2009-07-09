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
parser for Hands On Network
"""

# <VolunteerOpportunity>
# <LocalID>7702:76159:578625</LocalID>
# <AffiliateID>7702</AffiliateID>
# <OrgLocalID>578625</OrgLocalID>
# <Categories>
# <Category><CategoryID>5</CategoryID></Category>
# <Category><CategoryID>6</CategoryID></Category>
# </Categories>
# <DateListed>2008-07-08</DateListed>
# <OpportunityType><OpportunityTypeID>1</OpportunityTypeID></OpportunityType>
# <Title>HHSB Arts &amp; Crafts (FX)</Title>
# <DetailURL>http://www.HandsOnMiami.org/projects/viewProject.php?..</DetailURL>
# <Description>Join HOM at the Hebrew Home of South Beach </Description>
# <LogoURL>http://www.HandsOnMiami.org/uploaded_files/....gif</LogoURL>
# <LocationClassifications><LocationClassification><LocationClassificationID>1
# </LocationClassificationID></LocationClassification></LocationClassifications>
# <Locations>
# <Location>
# <Address1>Hebrew Home of South Beach</Address1>
# <Address2>320 Collins Avenue</Address2>
# <City>Miami Beach</City>
# <StateOrProvince>FL</StateOrProvince>
# <ZipOrPostalCode>33139</ZipOrPostalCode>
# <Country>USA</Country>
# </Location>
# </Locations>
# <OpportunityDates>
# <OpportunityDate>
# <StartDate>2008-08-09</StartDate>
# <EndDate>2008-08-09</EndDate>
# <StartTime>10:00:00</StartTime>
# <EndTime>11:30:00</EndTime>
# </OpportunityDate>
# <OpportunityDate>
# <StartDate>2008-08-23</StartDate>
# <EndDate>2008-08-23</EndDate>
# <StartTime>10:00:00</StartTime>
# <EndTime>11:30:00</EndTime>
# </OpportunityDate>
# </OpportunityDates>
# 
# <SponsoringOrganizations>
# <SponsoringOrganization>
# <Name>Hebrew Home of South Beach</Name>
# <Description>Hebrew Home of South Beach; Residential... </Description>
# <Country>USA</Country>
# <Phone>305-672-6464</Phone>
# <Extension>220</Extension>
# </SponsoringOrganization>
# </SponsoringOrganizations>
# </VolunteerOpportunity>

import xml_helpers as xmlh
import re
from datetime import datetime

# pylint: disable-msg=R0915
def parse(instr, maxrecs, progress):
  """return FPXML given handsonnetwork data"""
  if progress:
    print datetime.now(), "parse_handsonnetwork.Parse: starting parse..."
  known_elnames = [
    'Address1', 'Address2', 'AffiliateID', 'Categories', 'Category', 'City',
    'Country', 'DateListed', 'Description', 'DetailURL', 'EndDate', 'EndTime',
    'Extension', 'LocalID', 'Location', 'LocationClassifications',
    'Locations', 'LogoURL', 'Name', 'OpportunityDate', 'OpportunityDates',
    'OpportunityType', 'OrgLocalID', 'Phone', 'SponsoringOrganization',
    'SponsoringOrganizations', 'StartDate', 'StartTime', 'StateOrProvince',
    'Title', 'VolunteerOpportunity', 'ZipOrPostalCode'
    ]

  # convert to footprint format
  outstr = '<?xml version="1.0" ?>'
  outstr += '<FootprintFeed schemaVersion="0.1">'
  outstr += '<FeedInfo>'
  # TODO: assign provider IDs?
  outstr += '<providerID>102</providerID>'
  outstr += '<providerName>handsonnetwork.org</providerName>'
  outstr += '<feedID>1</feedID>'
  # TODO: get/create real feed date
  outstr += '<createdDateTime>%s</createdDateTime>' % xmlh.current_ts()
  outstr += '<providerURL>http://www.handsonnetwork.org/</providerURL>'
  outstr += '<description></description>'
  # TODO: capture ts -- use now?!
  outstr += '</FeedInfo>'

  numorgs = numopps = 0

  # hardcoded: Organization
  outstr += '<Organizations>'
  sponsor_ids = {}
  sponsorstrs = re.findall(
    r'<SponsoringOrganization>.+?</SponsoringOrganization>', instr, re.DOTALL)
  for i, orgstr in enumerate(sponsorstrs):
    if progress and i > 0 and i % 250 == 0:
      print str(datetime.now())+": ", i, " orgs processed."
    org = xmlh.simple_parser(orgstr, known_elnames, False)
    #sponsors = xmldoc.getElementsByTagName("SponsoringOrganization")
    #for i,org in enumerate(sponsors):
    outstr += '<Organization>'
    name = xmlh.get_tag_val(org, "Name")
    desc = xmlh.get_tag_val(org, "Description")
    outstr += '<organizationID>%d</organizationID>' % (i+1)
    outstr += '<nationalEIN></nationalEIN>'
    outstr += '<name>%s</name>' % (xmlh.get_tag_val(org, "Name"))
    outstr += '<missionStatement></missionStatement>'
    outstr += '<description>%s</description>' % \
        (xmlh.get_tag_val(org, "Description"))
    # unmapped: Email
    # unmapped: Phone
    # unmapped: Extension
    outstr += '<location>'
    #outstr += '<city>%s</city>' % (xmlh.get_tag_val(org, "City"))
    #outstr += '<region>%s</region>' % (xmlh.get_tag_val(org, "State"))
    #outstr += '<postalCode>%s</postalCode>' % \
    #   (xmlh.get_tag_val(org, "PostalCode"))
    outstr += '<country>%s</country>' % (xmlh.get_tag_val(org, "Country"))
    outstr += '</location>'
    outstr += '<organizationURL>%s</organizationURL>' % \
        (xmlh.get_tag_val(org, "URL"))
    outstr += '<donateURL></donateURL>'
    outstr += '<logoURL></logoURL>'
    outstr += '<detailURL></detailURL>'
    outstr += '</Organization>'
    numorgs += 1
    sponsor_ids[name+desc] = i+1
    
  outstr += '</Organizations>'
    
  outstr += '<VolunteerOpportunities>'
  #items = xmldoc.getElementsByTagName("VolunteerOpportunity")
  #if (maxrecs > items.length):
  #  maxrecs = items.length
  #for item in items[0:maxrecs-1]:
  if progress:
    print datetime.now(), "finding VolunteerOpportunities..."
  opps = re.findall(r'<VolunteerOpportunity>.+?</VolunteerOpportunity>',
                    instr, re.DOTALL)
  for i, oppstr in enumerate(opps):
    if (maxrecs > 0 and i > maxrecs):
      break
    xmlh.print_rps_progress("opps", progress, i, maxrecs)
    opp = xmlh.simple_parser(oppstr, known_elnames, False)
    orgs = opp.getElementsByTagName("SponsoringOrganization")
    name = xmlh.get_tag_val(orgs[0], "Name")
    desc = xmlh.get_tag_val(orgs[0], "Description")
    sponsor_id = sponsor_ids[name+desc]
    oppdates = opp.getElementsByTagName("OpportunityDate")
    if (oppdates == None or oppdates.count == 0):
      oppdates = [ None ]
    else: 
      # unmapped: LogoURL
      # unmapped: OpportunityTypeID   (categoryTag?)
      # unmapped: LocationClassificationID (flatten)
      datestr_pre = xmlh.output_val('volunteerOpportunityID', opp, "LocalID")
      datestr_pre = xmlh.output_plural('sponsoringOpportunityID', sponsor_id)
      # unmapped: OrgLocalID
      datestr_pre = xmlh.output_plural_node('volunteerHubOrganizationID', 
                                            opp, "AffiliateID")
      datestr_pre = xmlh.output_node('title', opp, "Title")
      datestr_pre += '<abstract></abstract>'
      datestr_pre += '<volunteersNeeded>-8888</volunteersNeeded>'
      
      locations = opp.getElementsByTagName("Location")
      if (locations.length != 1):
        print datetime.now(), "parse_handsonnetwork: only 1 location supported."
        return None
      loc = locations[0]
      datestr_post = '<locations><location>'
      # yuck, uses address1 for venue name... sometimes...
      #no way to detect: presence of numbers?
      datestr_post += xmlh.output_node('streetAddress1', loc, "Address1")
      datestr_post += xmlh.output_node('streetAddress2', loc, "Address2")
      datestr_post += xmlh.output_node('city', loc, "City")
      datestr_post += xmlh.output_node('region', loc, "State")
      datestr_post += xmlh.output_node('country', loc, "Country")
      datestr_post += xmlh.output_node('postalCode', loc, "ZipOrPostalCode")
      # no equivalent: latitude, longitude
      datestr_post += '</location></locations>'
      
      datestr_post += xmlh.output_node('detailURL', opp, "DetailURL")
      datestr_post += xmlh.output_node('description', opp, "Description")
      datestr_post += xmlh.output_val('lastUpdated', opp,
                 '%sT00:00:00' % (xmlh.get_tag_val(opp, "DateListed")))
       
      oppcount = 0
      datetimedur = ''
      for oppdate in oppdates:
        oppcount = oppcount + 1
        if progress:
          if numopps % 250 == 0:
            print datetime.now(), ": ", numopps, " records generated."
  
        datetimedur += '<dateTimeDuration>'
        if oppdate == None:
          datetimedur += '<openEnded>Yes</openEnded>'
        else:
          datetimedur += '<openEnded>No</openEnded>'
          # hardcoded: commitmentHoursPerWeek
          datetimedur += '<commitmentHoursPerWeek>0</commitmentHoursPerWeek>'
          # TODO: timezone
          datetimedur += xmlh.output_node("startDate", oppdate, "StartDate")
          datetimedur += xmlh.output_node("endDate", oppdate, "EndDate")
          datetimedur += xmlh.output_node("startTime", oppdate, "StartTime")
          datetimedur += xmlh.output_node("endTime", oppdate, "EndTime")
        datetimedur += '</dateTimeDuration>'
        
      if oppcount == 0: # insert an open ended datetimeduration
        datetimedur = '<dateTimeDuration><openEnded>'
        datetimedur += 'Yes</openEnded></dateTimeDuration>'
        
      outstr += '<VolunteerOpportunity>'
      outstr += datestr_pre
      outstr += '<dateTimeDurations>'
      outstr += datetimedur
      outstr += '</dateTimeDurations>'
      outstr += datestr_post
      outstr += '</VolunteerOpportunity>'
      numopps += 1
    
  outstr += '</VolunteerOpportunities>'
  outstr += '</FootprintFeed>'
  #outstr = re.sub(r'><([^/])', r'>\n<\1', outstr)
  return outstr, numorgs, numopps

