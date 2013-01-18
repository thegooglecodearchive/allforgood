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
parser for footprint itself (identity parse)
"""
import xml_helpers as xmlh
from datetime import datetime
import re

from pipeline import print_progress

# 90 days
DEFAULT_EXPIRATION = (90 * 86400)

# 10 years
DEFAULT_DURATION = (10 * 365 * 86400)

KNOWN_ELEMENTS = [
  'FeedInfo', 'FootprintFeed', 'Organization', 'Organizations',
  'VolunteerOpportunities', 'VolunteerOpportunity', 'abstract',
  'city', 'commitmentHoursPerWeek', 'contactEmail', 'contactName',
  'contactPhone', 'country', 'createdDateTime', 'dateTimeDuration',
  'dateTimeDurationType', 'dateTimeDurations', 'description',
  'detailURL', 'directions', 'donateURL', 'duration', 'email',
  'endDate', 'endTime', 'expires', 'fax', 'feedID', 'guidestarID',
  'iCalRecurrence', 'language', 'latitude', 'lastUpdated', 'location',
  'locationType', 'locations', 'logoURL', 'longitude', 'minimumAge',
  'missionStatement', 'name', 'nationalEIN', 'openEnded',
  'organizationID', 'organizationURL', 'paid', 'phone', 'postalCode',
  'providerID', 'providerName', 'providerURL', 'region',
  'schemaVersion', 'self_directed', 'sexRestrictedEnum', 'sexRestrictedTo', 
  'sponsoringOrganizationID', 'startDate', 'startTime', 'streetAddress1',
  'streetAddress2', 'streetAddress3', 'title', 'tzOlsonPath', 'virtual',
  'volunteerHubOrganizationID', 'volunteerOpportunityID',
  'volunteersFilled', 'volunteersSlots', 'volunteersNeeded', 'yesNoEnum',

  # HON 2012/05/24
  # http://www.avviato.net/afg/spec0.1.r1254_Sugested05242012.html
  'scheduleType', 
  'activityTypes', 'activityType',
  'populations', 'population', 
  'invitationCode', 
  'managedBy', 
  'opportunityType', 
  'registerType', 
  'affiliateId', 
  'isDisaster', 
  'frecuencyLink', 
  'frequencyLink', 

  'appropriateFors', 'appropriateFor', 
  'audienceTags', 'audienceTag', 
  'availabilityDays', 'dayWeek', 
  'skills', 'skill',
  'categoryTag', 'categoryTags',

  'eventId', 
  'eventName', 
  'occurrenceId', 
  'occurrenceDuration', 
  'hubOrganizationUrl', 
  'hubOrganizationName', 

  'impactArea',
  'organizationsServed',
  'additionalInfoRequired',
]

def set_default_time_elem(parent, entity, tagname, timest=xmlh.current_ts()):
  """footprint macro."""
  cdt = xmlh.set_default_value(parent, entity, tagname, timest)
  xmlh.set_default_attr(parent, cdt, "olsonTZ", "America/Los_Angeles")

def parse_fast(instr, maxrecs, progress):
  """fast parser but doesn't check correctness,
  i.e. must be pre-checked by caller."""
  numorgs = numopps = 0
  outstr_list = ['<?xml version="1.0" ?>']
  outstr_list.append('<FootprintFeed schemaVersion="0.1">')

  # note: processes Organizations first, so ID lookups work
  for match in re.finditer(re.compile('<FeedInfo>.+?</FeedInfo>',
                                      re.DOTALL), instr):
    node = xmlh.simple_parser(match.group(0), KNOWN_ELEMENTS, False)
    xmlh.set_default_value(node, node.firstChild, "feedID", "0")
    set_default_time_elem(node, node.firstChild, "createdDateTime")
    outstr_list.append(xmlh.prettyxml(node, True))

  outstr_list.append('<Organizations>')
  for match in re.finditer(re.compile('<Organization>.+?</Organization>',
                                      re.DOTALL), instr):
    node = xmlh.simple_parser(match.group(0), KNOWN_ELEMENTS, False)
    numorgs += 1
    outstr_list.append(xmlh.prettyxml(node, True))
  outstr_list.append('</Organizations>')
               
  outstr_list.append('<VolunteerOpportunities>')
  for match in re.finditer(re.compile(
      '<VolunteerOpportunity>.+?</VolunteerOpportunity>', re.DOTALL), instr):
    opp = xmlh.simple_parser(match.group(0), KNOWN_ELEMENTS, False)

    numopps += 1
    if (maxrecs > 0 and numopps > maxrecs):
      break
    #if progress and numopps % 250 == 0:
    #  print datetime.now(), ": ", numopps, " records generated."

    # these set_default_* functions dont do anything if the field
    # doesnt already exists
    xmlh.set_default_value(opp, opp, "volunteersNeeded", -8888)
    xmlh.set_default_value(opp, opp, "paid", "No")
    xmlh.set_default_value(opp, opp, "sexRestrictedTo", "Neither")
    xmlh.set_default_value(opp, opp, "language", "English")
    set_default_time_elem(opp, opp, "lastUpdated")
    set_default_time_elem(opp, opp, "expires", 
        xmlh.current_ts(DEFAULT_EXPIRATION))
   
    try:
      opplocs = opp.getElementsByTagName("location")
    except:
      opplocs = []

    for loc in opplocs:
      xmlh.set_default_value(opp, loc, "virtual", "No")
      xmlh.set_default_value(opp, loc, "country", "US")

    try:
      dttms = opp.getElementsByTagName("dateTimeDurations")
    except:
      dttms = []

    for dttm in dttms:
      # redundant xmlh.set_default_value(opp, dttm, "openEnded", "No")
      xmlh.set_default_value(opp, dttm, "iCalRecurrence", "")
      if (dttm.getElementsByTagName("startTime") == None and
          dttm.getElementsByTagName("endTime") == None):
        set_default_time_elem(opp, dttm, "timeFlexible", "Yes")
      else:
        set_default_time_elem(opp, dttm, "timeFlexible", "No")
      xmlh.set_default_value(opp, dttm, "openEnded", "No")

    try:
      time_elems = opp.getElementsByTagName("startTime")
      time_elems += opp.getElementsByTagName("endTime")
    except:
      time_elems = []

    for el in time_elems:
      xmlh.set_default_attr(opp, el, "olsonTZ", "America/Los_Angeles")

    str_opp = xmlh.prettyxml(opp, True)

    outstr_list.append(str_opp)

  outstr_list.append('</VolunteerOpportunities>')

  outstr_list.append('</FootprintFeed>')
  return "".join(outstr_list), numorgs, numopps

def parse(instr, maxrecs, progress):
  """return python DOM object given FPXML"""
  # parsing footprint format is the identity operation
  if progress:
    print datetime.now(), "parse_footprint: parsing ", len(instr), " bytes."
  xmldoc = xmlh.simple_parser(instr, KNOWN_ELEMENTS, progress)
  if progress:
    print datetime.now(), "parse_footprint: done parsing."
  return xmldoc

def parser(providerID, providerName, feedID, providerURL, feedDescription):
  """create an FPXML-compatible parser"""
  feedinfo = "<FeedInfo>"
  feedinfo += xmlh.output_val('providerID', providerID)
  feedinfo += xmlh.output_val('providerName', providerName)
  feedinfo += xmlh.output_val('feedID', feedID)
  feedinfo += xmlh.output_val('createdDateTime', xmlh.current_ts())
  feedinfo += xmlh.output_val('providerURL', providerURL)
  feedinfo += xmlh.output_val('description', feedDescription)
  feedinfo += "</FeedInfo>"
  def parse_func(instr, maxrecs, progress):
    """closure-- generated parse func"""
    outstr, numorgs, numopps = parse_fast(instr, maxrecs, progress)
    return re.sub(re.compile(r'<FeedInfo>.+?</FeedInfo>', re.DOTALL),
                  feedinfo, outstr), numorgs, numopps
  return parse_func
