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

# 90 days
DEFAULT_EXPIRATION = (90 * 86400)

# 10 years
DEFAULT_DURATION = (10 * 365 * 86400)

KNOWN_ELNAMES = [
  'FeedInfo', 'FootprintFeed', 'Organization', 'Organizations',
  'VolunteerOpportunities', 'VolunteerOpportunity', 'abstract', 'audienceTag',
  'audienceTags', 'categoryTag', 'categoryTags', 'city',
  'commitmentHoursPerWeek', 'contactEmail', 'contactName', 'contactPhone',
  'country', 'createdDateTime', 'dateTimeDuration', 'dateTimeDurationType',
  'dateTimeDurations', 'description', 'detailURL', 'directions', 'donateURL',
  'duration', 'email', 'endDate', 'endTime', 'expires', 'fax', 'feedID',
  'guidestarID', 'iCalRecurrence', 'language', 'latitude', 'lastUpdated',
  'location', 'locationType', 'locations', 'logoURL', 'longitude', 'minimumAge',
  'missionStatement', 'name', 'nationalEIN', 'openEnded', 'organizationID',
  'organizationURL', 'paid', 'phone', 'postalCode', 'providerID',
  'providerName', 'providerURL', 'region', 'schemaVersion', 'sexRestrictedEnum',
  'sexRestrictedTo', 'skills', 'sponsoringOrganizationID', 'startDate',
  'startTime', 'streetAddress1', 'streetAddress2', 'streetAddress3', 'title',
  'tzOlsonPath', 'virtual', 'volunteerHubOrganizationID',
  'volunteerOpportunityID', 'volunteersFilled', 'volunteersSlots',
  'volunteersNeeded', 'yesNoEnum'
  ]

def set_default_time_elem(parent, entity, tagname, timest=xmlh.current_ts()):
  """footprint macro."""
  cdt = xmlh.set_default_value(parent, entity, tagname, timest)
  xmlh.set_default_attr(parent, cdt, "olsonTZ", "America/Los_Angeles")

def parse_fast(instr, maxrecs, progress):
  """fast parser but doesn't check correctness,
  i.e. must be pre-checked by caller."""
  numorgs = numopps = 0
  outstr = '<?xml version="1.0" ?>'
  outstr += '<FootprintFeed schemaVersion="0.1">'

  # note: processes Organizations first, so ID lookups work
  feedchunks = re.findall(
    re.compile('<FeedInfo>.+?</FeedInfo>', re.DOTALL), instr)
  for feedchunk in feedchunks:
    node = xmlh.simple_parser(feedchunk, KNOWN_ELNAMES, False)
    xmlh.set_default_value(node, node.firstChild, "feedID", "0")
    set_default_time_elem(node, node.firstChild, "createdDateTime")
    outstr += xmlh.prettyxml(node, True)

  orgchunks = re.findall(
    re.compile('<Organization>.+?</Organization>', re.DOTALL), instr)
  outstr += '<Organizations>'
  for orgchunk in orgchunks:
    node = xmlh.simple_parser(orgchunk, KNOWN_ELNAMES, False)
    numorgs += 1
    outstr += xmlh.prettyxml(node, True)
  outstr += '</Organizations>'
               
  oppchunks = re.findall(
    re.compile('<VolunteerOpportunity>.+?</VolunteerOpportunity>',
               re.DOTALL), instr)
  outstr += '<VolunteerOpportunities>'
  for oppchunk in oppchunks:
    opp = xmlh.simple_parser(oppchunk, KNOWN_ELNAMES, False)
    numopps += 1
    if (maxrecs > 0 and numopps > maxrecs):
      break
    if progress and numopps % 250 == 0:
      print datetime.now(), ": ", numopps, " records generated."
    xmlh.set_default_value(opp, opp, "volunteersNeeded", -8888)
    xmlh.set_default_value(opp, opp, "paid", "No")
    xmlh.set_default_value(opp, opp, "sexRestrictedTo", "Neither")
    xmlh.set_default_value(opp, opp, "language", "English")
    set_default_time_elem(opp, opp, "lastUpdated")
    set_default_time_elem(opp, opp, "expires", 
                          xmlh.current_ts(DEFAULT_EXPIRATION))
    for loc in opp.getElementsByTagName("location"):
      xmlh.set_default_value(opp, loc, "virtual", "No")
      xmlh.set_default_value(opp, loc, "country", "US")
    for dttm in opp.getElementsByTagName("dateTimeDurations"):
      xmlh.set_default_value(opp, dttm, "openEnded", "No")
      xmlh.set_default_value(opp, dttm, "iCalRecurrence", "")
      if (dttm.getElementsByTagName("startTime") == None and
          dttm.getElementsByTagName("endTime") == None):
        set_default_time_elem(opp, dttm, "timeFlexible", "Yes")
      else:
        set_default_time_elem(opp, dttm, "timeFlexible", "No")
      xmlh.set_default_value(opp, dttm, "openEnded", "No")
    time_elems = opp.getElementsByTagName("startTime")
    time_elems += opp.getElementsByTagName("endTime")
    for el in time_elems:
      xmlh.set_default_attr(opp, el, "olsonTZ", "America/Los_Angeles")
    outstr += xmlh.prettyxml(opp, True)
  outstr += '</VolunteerOpportunities>'

  outstr += '</FootprintFeed>'
  return outstr, numorgs, numopps

def parse(instr, maxrecs, progress):
  """return python DOM object given FPXML"""
  # parsing footprint format is the identity operation
  # TODO: maxrecs
  # TODO: progress
  if progress:
    print datetime.now(), "parse_footprint: parsing ", len(instr), " bytes."
  xmldoc = xmlh.simple_parser(instr, KNOWN_ELNAMES, progress)
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
    outstr, numorgs, numopps = parse_fast(instr, maxrecs, progress)
    return re.sub(re.compile(r'<FeedInfo>.+?</FeedInfo>', re.DOTALL),
                  feedinfo, outstr), numorgs, numopps
  return parse_func
