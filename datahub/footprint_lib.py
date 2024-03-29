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
main() for the crawling/parsing/loading pipeline
"""
#from xml.dom.ext import PrettyPrint
import os
import gzip
import hashlib
import urllib2
import re
import random
import htmlentitydefs
import xml.sax.saxutils as saxutils
import json

import subprocess
import sys
import xml_helpers as xmlh
from datetime import datetime
import geocoder_mapsV3 as geocoder
from optparse import OptionParser
from BeautifulSoup import BeautifulSoup

import dateutil
import dateutil.tz
import dateutil.parser

import parse_footprint
import parse_gspreadsheet as gsp
import parse_usaservice
import parse_networkforgood
import parse_idealist
import parse_craigslist
import parse_350org
import parse_sparked
import parse_diy
import parse_volunteermatch
import providers
import check_links

import utf8

from taggers import get_taggers, XMLRecord
from spreadsheets.process import sheet_list
from directfields import DIRECT_FIELDS

FIELDSEP = "\t"
RECORDSEP = "\n"
FED_DIR = 'fed/'
EIN_DIR = 'ein/'
# 7 days
DEFAULT_EXPIRES = (7 * 86400)

MAX_ABSTRACT_LEN = 300

DEBUG = False
PROGRESS = False
PRINTHEAD = False
OUTPUTFMT = "fpxml"

NUMORGS = 0
DUPS = 0
NOLOC = 0
EIN501 = 0

FEED = ''
FEEDSDIR = 'feeds'
DUPDIR = 'dups' 

IGNORE_DUPLICATES = False


# set a nice long timeout
import socket
socket.setdefaulttimeout(600.0)

# pick a latlng that'll never match real queries
UNKNOWN_LAT = UNKNOWN_LNG = "-10"
UNKNOWN_LATLNG = UNKNOWN_LAT + "," + UNKNOWN_LNG

# pick a latlng that'll never match real queries
LOCATIONLESS_LAT = LOCATIONLESS_LNG = "0"
LOCATIONLESS_LATLNG = LOCATIONLESS_LAT + "," + LOCATIONLESS_LNG

HEADER_ALREADY_OUTPUT = False

FIELDTYPES = {  #Describes all the fields and their available in the footprint file
  "title":"builtin",
  "description":"builtin",
  "link":"builtin",
  "event_type":"builtin",
  "quantity":"builtin",
  "image_link":"builtin",
  "event_date_range":"builtin",
  "id":"builtin",
  "location":"builtin",

  "paid":"boolean",
  "openended":"boolean",

  "volunteersSlots":"integer",
  "volunteersFilled":"integer",
  "volunteersNeeded":"integer",
  "rsvpCount":"integer",
  "minimumAge":"integer",
  "startTime":"integer",
  "endTime":"integer",
  "ical_recurrence":"string",

  "latitude":"float",
  "longitude":"float",
  "latlong":"string",
  #"location_0_coordinate":"float",
  #"location_1_coordinate":"float",
  "virtual":"boolean",
  "self_directed":"boolean",
  "micro":"boolean",
  "is_501c3":"boolean",

  "providerURL":"URL",
  "detailURL":"URL",
  "org_organizationURL":"URL",
  "org_logoURL":"URL",
  "org_providerURL":"URL",
  "feed_providerURL":"URL",

  "lastUpdated":"dateTime",
  "expires":"dateTime",
  "feed_createdDateTime":"dateTime",

  "duration":"string",
  "abstract":"string",
  "sexRestrictedTo":"string",
  "contactName":"string",
  "contactPhone":"string",
  "contactEmail":"string",
  "language":"string",
  "org_name":"string",
  "org_missionStatement":"string",
  "org_description":"string",
  "org_phone":"string",
  "org_fax":"string",
  "org_email":"string",
  "audiences":"string",
  "commitmentHoursPerWeek":"string",
  "employer":"string",
  "feed_providerName":"string",
  "feed_description":"string",
  "providerID":"string",
  "feed_providerID":"string",
  "feedID":"string",
  "volunteerOpportunityID":"string",
  "OpportunityID":"string",
  "occurrenceId":"string",
  "organizationID":"string",
  "sponsoringOrganizationID":"strng",
  "volunteerHubOrganizationID":"string",
  "volunteerAffiliateOrganizationID":"string",
  "org_nationalEIN":"string",
  "org_guidestarID":"string",
  "venue_name":"string",

  "city":"string",
  "county":"string",
  "state":"string",
  "zip":"string",
  "country":"string",
  "statewide":"string",
  "nationwide":"string",

  "location_string":"string",
  "given_location":"string",
  "orgLocation":"string",
  "provider_proper_name":"string",

  # HON 2012/05/24
  # http://www.avviato.net/afg/spec0.1.r1254_Sugested05242012.html
  "scheduleType":"string",
  "activityTypes":"string",
  "activityType":"string",
  "population":"string",
  "invitationCode":"string",
  "managedBy":"string",
  "registerType":"string",

  "volunteerHubOrganizationURL" : "string",
  "volunteerHubOrganizationName" : "string",

  "affiliateOrganizationURL" : "string",
  "affiliateOrganizationName" : "string",
  "affiliateOrganizationID" : "string",

  "eventId":"string",
  "eventName":"string",

  "occurrenceDuration":"string",
  "occurrenceId":"string",

  "isDisaster":"string",
  "opportunityType":"string",
  "frecuencyLink":"string",
  "frequencyLink":"string",
  "frequencyURL":"string",
  "frequency":"string",
  "appropriateFors":"string",
  "appropriateFor":"string",
  "audienceTags":"string",
  "audienceTag":"string",
  "categories":"string",
  "categoryTags":"string",
  "categoryTag":"string",
  "populations":"string",
  "population":"string",
  "availabilityDays":"string",
  "dayWeek":"string",
  "skills":"string",
  "skill":"string",
  "additionalInfoRequired":"boolean",

  "impactArea":"string",
  "impactAreas":"string",
  "organizationsServed":"string",
}

ORGANIZATION_FIELDS = [                                                                                  
  'nationalEIN', 'guidestarID', 'name', 'missionStatement', 'description',                               
  'phone', 'fax', 'email', 'organizationURL', 'logoURL', 'providerURL',                                  
]                                                                                                        
                                                                                                         
MAPPED_FIELDS = {
  'rsvpCount' : 'volunteersFilled' , 
  'volunteersNeeded' : 'volunteersSlots',
  'appropriateFor' : 'appropriateFors',
  'audienceTag' : 'audienceTags',
  'categoryTag' : 'categoryTags',
  'dayWeek' : 'availabilityDays',
  'activityType' : 'activityTypes',
  'population' : 'populations',
  'skill' : 'skills',
}
                                                                                                         
def print_progress(msg, filename="", progress=None):
  """print progress indicator."""
  # not allowed to say progress=PROGRESS as a default arg
  if progress is None:
    progress = PROGRESS
  xmlh.print_progress(msg, filename, progress=progress)

def print_status(msg, filename="", progress=None):
  """print status indicator, for stats collection."""
  if progress is None:
    progress = PROGRESS
  xmlh.print_status(msg, filename, progress=progress)

def print_debug(msg):
  """print debug message."""
  if DEBUG:
    print datetime.now(), msg

# Google Base uses ISO8601... in PST -- I kid you not:
# http://base.google.com/support/bin/answer.py?
# answer=78170&hl=en#Events%20and%20Activities
# and worse, you have to change an env var in python...
def convert_dt_to_gbase(datestr, timestr, timezone):
  """converts dates like YYYY-MM-DD, times like HH:MM:SS and
  timezones like America/New_York, into Google Base format."""
  if datestr.find('0000') == 0:
    return datestr

  dflt = '2000-01-01T00:00:00'
  try:
    try:
      tzinfo = dateutil.tz.tzstr(timezone)
    except:
      tzinfo = dateutil.tz.tzutc()

    timestr = dateutil.parser.parse(datestr + " " + timestr)
    timestr = timestr.replace(tzinfo=tzinfo)
    utc = dateutil.tz.tzutc()
    timestr = timestr.astimezone(utc)
    res = timestr.strftime("%Y-%m-%dT%H:%M:%S")
    res = re.sub(r'Z$', '', res)
    return res
  except:
    pass

  return dflt


def output_field(name, given_value):
  """print a field value, handling long strings, header lines and
  custom datatypes."""
  global FIELDTYPES

  if name not in FIELDTYPES:
    print datetime.now(), "no type for field? " + name + " (assuming string)"
    #return name
    FIELDTYPES[name] = 'string'
    if PRINTHEAD:
      return name + ":string"
    
  if PRINTHEAD:
    if FIELDTYPES.get(name, 'string') == "builtin":
      return name
    elif OUTPUTFMT == "basetsv":
      return "c:"+name+":"+FIELDTYPES.get(name, 'string')
    else:
      return name+":"+FIELDTYPES.get(name, 'string')

  value = given_value

  # common fixup for URL fields
  if re.search(r'url', name, re.IGNORECASE):
    # common error in datafeeds: http:///
    value = re.sub(r'http:///', 'http://', value)
    if value != "" and not re.search(r'^https?://', value):
      # common error in datafeeds: missing leading http://
      value = "http://" + value
    # common error in datafeeds: http://http://
    value = re.sub(r'http://http://', 'http://', value)

  # fixes for Scott Stewart 
  if re.search(r'americorps\.org', value, re.IGNORECASE):
    value = re.sub(r'(?i)americorps\.org', 'americorps.gov', value)
    print_progress("replaced americorps")

  if re.search(r'learnandserve\.org', value, re.IGNORECASE):
    value = re.sub(r'(?i)learnandserve\.org', 'learnandserve.gov', value)
    print_progress("replaced learnandserve")

  if re.search(r'seniorcorps\.org', value, re.IGNORECASE):
    value = re.sub(r'(?i)seniorcorps\.org', 'seniorcorps.gov', value)
    print_progress("replaced seniorcorps")

  if (not re.search(r'musicnationalservice\.org', value, re.IGNORECASE)
      and re.search(r'nationalservice\.org', value, re.IGNORECASE)):
    value = re.sub(r'(?i)nationalservice\.org', 'nationalservice.gov', value)
    print_progress("replaced nationalservice")
    
  #if OUTPUTFMT == "basetsv":
  #  value = re.sub(r',', ';;', value)

  if (FIELDTYPES.get(name, 'string') == "dateTime"):
    return convert_dt_to_gbase(value, "", "UTC")

  value = value.replace('\n', ' ')
  return value


def get_addr_field(node, field):
  """assuming a node is named (field), return it with optional trailing spc."""
  addr = xmlh.get_tag_val(node, field)
  if addr != "":
    addr += " "
  return addr


def get_city_addr_str(node):
  """synthesize a city-region-postal-country string."""
  # note: avoid commas, so it works with csv
  loc = ""
  loc += get_addr_field(node, "city")
  loc += get_addr_field(node, "region")
  loc += get_addr_field(node, "postalCode")
  loc += get_addr_field(node, "country")
  return loc


def get_street_addr_str(node):
  """concatenate street address fields"""
  loc = get_addr_field(node, "streetAddress1")
  loc += get_addr_field(node, "streetAddress2")
  loc += get_addr_field(node, "streetAddress3")
  return loc


def get_full_addr_str(node):
  """concatenate street address and city/region/postal/country fields"""
  loc = get_street_addr_str(node)
  loc += get_city_addr_str(node)
  return loc


JO_SAID = {}
def get_revgeo_fields(lat, lng, given_city, given_county, given_state, given_zip, given_country):
  
  city = given_city
  county = given_county
  state = given_state 
  zip = given_zip
  country = given_country
  if not country:
    country = 'US'

  jo = geocoder.rev_geocode_json(lat, lng, None, 0, JO_SAID)
  if jo and 'status' in jo:
    if jo['status'] != "OK":
      if jo['status'] == 'ZERO_RESULTS':
        say = "rev_geocode_json: says " + jo['status'] + ' for ' + str(lat) + ',' + str(lng)
        if say not in JO_SAID:
          JO_SAID[say] = 1
          print say
      elif not jo['status'] in JO_SAID:
        JO_SAID[jo['status']] = 1
        print "rev_geocode_json: says " + jo['status']
    else:
      for d in jo['results'][0]['address_components']:
        if 'locality' in d['types']:
          city = d['long_name']
        elif 'postal_code' in d['types']:
          if not given_zip or len(given_zip) < 5:
            zip = d['short_name']
          else:
            zip = given_zip[:5]
        elif 'administrative_area_level_1' in d['types']:
          state = d['short_name']
        elif 'administrative_area_level_2' in d['types']:
          county = d['short_name']
        elif 'country' in d['types']:
          country = d['short_name']

  if state and country and country != 'US':
     state += '-' + country

  return city.strip(), county.strip(), state.strip(), zip.strip(), country.strip()
  

def find_geocoded_location(node):
  """Try a multitude of field combinations to get a geocode.  Returns:
  address, latitude, longitude, accuracy (as strings)."""
  
  # Combinations of fields to try geocoding.
  field_combinations = \
      ["streetAddress1,streetAddress2,streetAddress3,"
       + "city,region,postalCode,country",
       "streetAddress2,streetAddress3,"
       + "city,region,postalCode,country",
       "streetAddress3,city,region,postalCode,country",
       "city,region,postalCode,country",
       "postalCode,country",
       "city,region,country",
       "region,country",
       "latitude,longitude"]

  # Upper bound on the accuracy provided by a given field.  This
  # prevents false positives like matching the city field to a street
  # name.
  field_accuracy = { "streetAddress1": 9,
                     "streetAddress2": 9,
                     "streetAddress3": 9,
                     "city": 5,
                     "region": 5,
                     "postalCode": 5,
                     "country": 1,
                     "latitude": 9,
                     "longitude": 9 }

  for fields in field_combinations:
    field_list = fields.split(",")

    # Compose the query and find the max accuracy.
    query = []
    max_accuracy = 0
    for field in field_list:
      field_val = xmlh.get_tag_val(node, field)
      if field_val != "":
        query += [field_val]
        max_accuracy = max(max_accuracy, field_accuracy[field])
    query = ",".join(query)

    print_debug("trying: " + query + " (" + str(max_accuracy) + ")")
    result = geocoder.geocode(query)
    if result:
      addr, lat, lng, acc = result
      if int(acc) <= max_accuracy:
        print_debug("success: " + str(result))
        return result
      print_debug("incorrect accuracy: " + str(result))

  result = (get_full_addr_str(node), "0.0", "0.0", "0")
  print_debug("failed: " + str(result))
  return result


def output_loc_field(node, mapped_name):
  """macro for output_field( convert node to loc field )"""
  return output_field(mapped_name, 
                      get_street_addr_str(node)+get_city_addr_str(node))

def output_tag_value(node, fieldname):
  """macro for output_field( get node value )"""
  return output_field(fieldname, xmlh.get_tag_val(node, fieldname))


def output_tag_value_renamed(node, xmlname, newname):
  """macro for output_field( get node value ) then emitted as newname"""
  return output_field(newname, xmlh.get_tag_val(node, xmlname))


def feed_report(id, detail, feed = None, link = None):
  """ """

  if not feed:
    feed = FEED

  if id and detail and feed:
    file = FEEDSDIR + '/' + feed + '-' + detail + '-last.txt'
    try:
      fh = open(file, 'a')
    except:
      fh = None

    if fh:
      fh.write(str(id).ljust(23))
      if link:
        link = str(link)
        fh.write('\t<a target="_blank" href="' + link + '">' + link + '</a>')
        #link_file = check_links.DIR_BAD + check_links.get_link_file_name(link)
        #fh.write('\t' + time.mtime(os.path.getmtime(link_file)))
      fh.write('\n')
      fh.close()
  
# Removes duplicates comparing title, abstract, loc_str, startend
def duplicate_opp(opp, loc_str, startend):
  rtn = False
  if IGNORE_DUPLICATES:
    return rtn
  title = get_title(opp).lower()
  abstract = get_abstract(opp).lower()
  #dedup_str = "".join([title, desc, detailURL, loc_str, startend])
  dedup_str = "".join([title, abstract, loc_str, startend])
  dedup_file = DUPDIR + '/' + hashlib.md5(dedup_str).hexdigest()
  if os.path.exists(dedup_file): 
    global DUPS
    DUPS += 1
    opp_id = xmlh.get_tag_val(opp, "volunteerOpportunityID")
    if opp_id:
      link = xmlh.get_tag_val(opp, 'detailURL')
      feed_report(opp_id, 'duplicates', FEED, link)
    rtn = True
  else:
    try:
      open(dedup_file, 'w').close()
    except:
      pass

  return rtn


def compute_stable_id(opp, org, loc_str, openended, duration,
                      hrs_per_week, startend):
  """core algorithm for computing an opportunity's unique id."""
  if DEBUG:
    print "opp=" + str(opp)  # shuts up pylint
  eid = xmlh.get_tag_val(org, "nationalEIN")
  if (eid == ""):
    # support informal "organizations" that lack EINs
    eid = xmlh.get_tag_val(org, "organizationURL")
  stripped_loc = stripped_string = re.sub('\d+', '', loc_str)

  timestr = openended + duration + hrs_per_week + startend
  title = get_title(opp)
  abstract = get_abstract(opp)
  description = xmlh.get_tag_val(opp, 'description')
  detailURL = xmlh.get_tag_val(opp, 'detailURL')
  hashstr = "\t".join([eid,
                      stripped_loc,
                      timestr,
                      title,
                      abstract,
                      detailURL,
                      description])

   
  return hashlib.md5(hashstr).hexdigest()


def get_abstract(opp):
  """process abstract-- shorten, strip newlines and formatting."""
  abstract = xmlh.get_tag_val(opp, "abstract")
  if abstract == "":
    abstract = xmlh.get_tag_val(opp, "description")
  abstract = cleanse_snippet(abstract)
  return abstract[:MAX_ABSTRACT_LEN]


def get_501c3_status(ein):
  """ a place holder until we get access to real data """
  rtn = 'False'
  if ein:
    match = re.search(r'(\b\d{2}-?\d{7}\b)', ein)
    if match:
      ein9 = match.group(1).replace('-', '')
      if os.path.isfile(EIN_DIR + ein9):
        #print_progress('501(c)3: ' + ein9)
        global EIN501
        EIN501 += 1
        rtn = 'True'

  return rtn


def get_direct_mapped_fields(opp, orgs, feed_providerName):
  """map a field directly from FPXML to Google Base."""
  outstr = output_field("abstract", get_abstract(opp))

  paid = xmlh.get_tag_val(opp, "paid")
  if (paid == "" or paid.lower()[0] != "y"):
    paid = "n"
  else:
    paid = "y"
  outstr += FIELDSEP + output_field("paid", paid)

  # additionalInfoRequired requires special handling to convert values to boolean
  additionalInfoRequired = xmlh.get_tag_val(opp, "additionalInfoRequired")
  if (additionalInfoRequired == "" or additionalInfoRequired.lower()[0] != "y"):
    additionalInfoRequired = "False"
  else:
    additionalInfoRequired = "True"
  outstr += FIELDSEP + output_field("additionalInfoRequired", additionalInfoRequired)
  
  # self_directed requires special handling to convert values to boolean
  self_directed = xmlh.get_tag_val(opp, "self_directed")
  if (self_directed == "" or self_directed.lower()[0] != "y"):
    self_directed = "False"
  else:
    self_directed = "True"
  outstr += FIELDSEP + output_field("self_directed", self_directed)

  # micro requires special handling to convert values to boolean
  micro = xmlh.get_tag_val(opp, "micro")
  if (micro == "" or micro.lower()[0] != "y"):
    micro = "False"
  else:
    micro = "True"
  outstr += FIELDSEP + output_field("micro", micro)

  detailURL = xmlh.get_tag_val(opp, "detailURL")
  outstr += FIELDSEP + output_field("detailURL", detailURL)

  # Process all tags according to the fields declared in DIRECT_FIELDS
  for field in DIRECT_FIELDS:
    if field == 'OpportunityID':
      if PRINTHEAD:
        outstr += FIELDSEP + output_tag_value(opp, field)
      else:
        opp_id = xmlh.get_tag_val(opp, "volunteerOpportunityID")
        if not opp_id:
          opp_id = 'volunteerOpportunityID'
        outstr += FIELDSEP + output_field('OpportunityID', opp_id)
    elif field == "expires":
      # we need to have a expires value
      expires = xmlh.get_tag_val(opp, "expires")
      if PRINTHEAD or len(expires) > 0:
        outstr += FIELDSEP + output_tag_value(opp, field)
      else:
        outstr += FIELDSEP + xmlh.current_ts(DEFAULT_EXPIRES)
    elif field in MAPPED_FIELDS:
      if PRINTHEAD:
        outstr += FIELDSEP + output_tag_value(opp, MAPPED_FIELDS[field])
      else:
        value = output_tag_value(opp, field)
        if field == 'categoryTag':
          #print field + '=' + '"' + value + '"'
          value = value.replace('; ', '|')
        outstr += FIELDSEP + value
    else:
      outstr += FIELDSEP + output_tag_value(opp, field)

  # skills/skill requires special handling because 2.12 introduced a design bug that allowed to declare it as an array of skill tags or not
  skillTag = opp.getElementsByTagName("skill")

  if (skillTag.length > 0):
    value = output_tag_value_renamed(opp, "skill", "skills")
    # Strip apostrophe or the upload to SOLR will fail
    value = value.replace("'", "")
    outstr += FIELDSEP + value
  else:
    value = output_tag_value(opp, "skills")
    # Strip apostrophe or the upload to SOLR will fail
    value = value.replace("'", "")
    outstr += FIELDSEP + value

  for field in ORGANIZATION_FIELDS:
    outstr += FIELDSEP + output_field("org_"+field,
                                       xmlh.get_tag_val(orgs[0], field))
    if field == 'nationalEIN':
      ein = xmlh.get_tag_val(orgs[0], field)
      is_501c3 = get_501c3_status(ein)
      outstr += FIELDSEP + output_field("is_501c3", is_501c3)
   
  # orgLocation
  outstr += FIELDSEP
  fieldval = opp.getElementsByTagName("orgLocation")
  if (fieldval.length > 0):
    outstr += output_loc_field(fieldval[0], "orgLocation")
  else:
    outstr += output_field("orgLocation", "")

  # map providerName to provider_proper_name
  outstr += FIELDSEP
  ppn = "Additional Partners"
  if providers.ProviderNames.has_key(feed_providerName):
    ppn = providers.ProviderNames[feed_providerName]["name"]
  outstr += output_field("provider_proper_name", str(ppn))

  # hubOrg
  for fd in [{'s' : 'Name' , 'f' : 'name'}, {'s': 'URL', 'f' : 'organizationURL'}]:
    outstr += FIELDSEP
    if orgs[1]:
      outstr += output_field("volunteerHubOrganization" + fd['s'], xmlh.get_tag_val(orgs[1], fd['f']))
    elif PRINTHEAD:
      outstr += "volunteerHubOrganization" + fd['s']

  # affiliateOrg
  for fd in [{'s' : 'Name' , 'f' : 'name'}, {'s': 'URL', 'f' : 'organizationURL'}]:
    outstr += FIELDSEP
    if orgs[2]:
      outstr += output_field("affiliateOrganization" + fd['s'], xmlh.get_tag_val(orgs[2], fd['f']))
    elif PRINTHEAD:
      outstr += "affiliateOrganization" + fd['s']

  return outstr


def get_base_other_fields(opp, org):
  """These are fields that exist in other Base schemas-- for the sake of
  possible syndication, we try to make ourselves look like other Base
  feeds.  Since we're talking about a small overlap, these fields are
  populated *as well as* direct mapping of the footprint XML fields."""
  outstr = output_field("employer", xmlh.get_tag_val(org, "name"))
  outstr += FIELDSEP + output_field("quantity",
                         xmlh.get_tag_val(opp, "volunteersNeeded"))
  outstr += FIELDSEP + output_field("image_link",
                                    xmlh.get_tag_val(org, "logoURL"))
  # don't map expiration_date -- Base has strict limits (e.g. 2 weeks)
  return outstr


html_tag_rx = re.compile(r'<.*?>')
sent_start_rx = re.compile(r'((^\s*|[.]\s+)[A-Z])([A-Z0-9 ,;-]{13,})')
def cleanse_snippet(instr):

  if instr:
    # strip \n and \b
    instr = re.sub(r'(\\[bn])+', ' ', instr)
    instr = re.sub(r'\\n', ' ', instr)
    instr = re.sub(r'\n', ' ', instr)
    # replace some common entities with their ascii equivalents
    instr = re.sub(r'&(uml|middot|ndash|bull|mdash|hellip);', '-', instr)
    # unescape always replaces &amp; &lt; and &gt; then we add &nbsp;
    instr = saxutils.unescape(instr, {'&nbsp;':' '})
    # best chance to handle malformed html and still get contents
    instr = ''.join(BeautifulSoup(instr).findAll(text=True))
    # TODO: only ascii allowed but will need to accomdate i8n eventually
    instr = "".join(i for i in instr if ord(i)<128)
    # strip any remaining html entities
    instr = re.sub(r'&([a-z]+|#[0-9]+);', '', instr)
    instr = html_tag_rx.sub('', instr)
    # last resort - whatever it is, it will not be html
    instr = re.sub(r'<.', '', instr)
    instr = re.sub(r'.>', '', instr)
    instr = re.sub(r'>', '', instr)
    instr = re.sub(r'<', '', instr)
    # strip repeated spaces, so maxlen works
    instr = re.sub(r'\s+', ' ', instr)
    # fix obnoxious all caps titles and snippets
    for str in re.finditer(sent_start_rx, instr):
      instr = re.sub(sent_start_rx, str.group(1)+str.group(3).lower(), instr, 1)

  return instr


def get_title(opp):
  """compute a clean title. """
  title = cleanse_snippet(output_tag_value(opp, "title"))
  for str in re.finditer(lcword_rx, title):
    title = re.sub(lcword_rx, str.group(1)+str.group(2).upper(), title, 1)
  return title

lcword_rx = re.compile(r'(\s)([a-z])')
def get_event_reqd_fields(opp):
  """Fields required by Google Base, note that they aren't necessarily
  used by the FP app."""
  outstr = get_title(opp)
  outstr += FIELDSEP + output_tag_value(opp, "description")
  return outstr

def get_feed_fields(feedinfo):
  """Fields from the <Feed> portion of FPXML."""
  feed_providerName = output_tag_value_renamed(feedinfo,
                                    "providerName", "feed_providerName")
  outstr = feed_providerName

  outstr += FIELDSEP + output_tag_value(feedinfo, "feedID")
  outstr += FIELDSEP + output_tag_value_renamed(
    feedinfo, "providerID", "feed_providerID")
  outstr += FIELDSEP + output_tag_value_renamed(
    feedinfo, "providerURL", "feed_providerURL")
  outstr += FIELDSEP + output_tag_value_renamed(
    feedinfo, "description", "feed_description")
  outstr += FIELDSEP + output_tag_value_renamed(
    feedinfo, "createdDateTime", "feed_createdDateTime")
  return outstr, feed_providerName


def output_opportunity(opp, feedinfo, known_orgs, totrecs):
  """main function for outputting a complete opportunity."""
  outstr_list = []
  opp_id = xmlh.get_tag_val(opp, "volunteerOpportunityID")
  if (opp_id == ""):
    print_progress("no opportunityID")
    return totrecs, ""

  sponsoring_org_id = xmlh.get_tag_val(opp, "sponsoringOrganizationID")
  hub_org_id = xmlh.get_tag_val(opp, "volunteerHubOrganizationID")
  if not hub_org_id:
    hub_org_id = xmlh.get_tag_val(opp, "hubOrganizationID")

  if sponsoring_org_id not in known_orgs:
    sponsoring_org_id = hub_org_id

  if sponsoring_org_id not in known_orgs:
    print_progress('unknown sponsoringOrganizationID: "' + sponsoring_org_id + '"  skipping opportunity ' + opp_id)
    return totrecs, ""

  affiliate_org_id = xmlh.get_tag_val(opp, "affiliateId")
  if not affiliate_org_id:
    affiliate_org_id = xmlh.get_tag_val(opp, "affiliateOrganizationID")

  orgs = [known_orgs[sponsoring_org_id],
          known_orgs.get(hub_org_id, None),
          known_orgs.get(affiliate_org_id, None),
         ]

  opp_locations = opp.getElementsByTagName("location")
  opp_times = opp.getElementsByTagName("dateTimeDuration")
  repeated_fields = get_repeated_fields(feedinfo, opp, orgs)

  number_of_opptimes = len(opp_times)
  if number_of_opptimes == 0:
    opp_opptimes = [ None ]
  elif number_of_opptimes > 1:
    xmlh.processing_trace("footprint_lib.output_opportunity",
                          "unwound %g dates from %s:%s" 
                          % (number_of_opptimes, sponsoring_org_id, opp_id))

  link = xmlh.get_tag_val(opp, 'detailURL')

  for opptime in opp_times:
    # unwind multiple dates
    if opptime is None:
      startend = convert_dt_to_gbase("2000-01-01", "00:00:00-00:00", "UTC")
      starttime = "0000"
      endtime = "2359"
      openended = "Yes"
    else:
      # event_date_range
      # e.g. 2006-12-20T23:00:00/2006-12-21T08:30:00, in PST (GMT-8)
      start_date = xmlh.get_tag_val(opptime, "startDate")
      start_time = xmlh.get_tag_val(opptime, "startTime")
      end_date = xmlh.get_tag_val(opptime, "endDate")
      end_time = xmlh.get_tag_val(opptime, "endTime")
      openended = xmlh.get_tag_val(opptime, "openEnded")
      ical_recurrence = xmlh.get_tag_val(opptime, "iCalRecurrence")
      # e.g. 2006-12-20T23:00:00/2006-12-21T08:30:00, in PST (GMT-8)
      if (start_date == ""):
        start_date = "2000-01-01"
        start_time = "00:00:00-00:00"
      startend = convert_dt_to_gbase(start_date, start_time, "UTC")
      #if (end_date != "" and end_date + end_time > start_date + start_time):
      if end_date:
        endstr = convert_dt_to_gbase(end_date, end_time, "UTC")
        startend += "/" + endstr

    duration = xmlh.get_tag_val(opptime, "duration")
    hrs_per_week = xmlh.get_tag_val(opptime, "commitmentHoursPerWeek")
    time_fields = get_time_fields(openended, duration, hrs_per_week, startend, ical_recurrence)

    number_of_locations = len(opp_locations)
    if number_of_locations == 0:
      opp_locations = [ None ]
    elif number_of_locations > 1:
      xmlh.processing_trace("footprint_lib.output_opportunity",
                            "unwound %g locations, %g date(s) from %s:%s" 
                            % (number_of_locations, number_of_opptimes, 
                               sponsoring_org_id, opp_id))

    for opploc in opp_locations:
      # unwind multiple locations
      if opploc is None:
        loc_str, latlng, geocoded_loc = ("", "", "")
        loc_fields = get_loc_fields(virtual="No", latitude="0.0", longitude="0.0")
      else:
        loc_str = get_full_addr_str(opploc)
        addr, lat, lng, acc = find_geocoded_location(opploc)

        given_address = get_street_addr_str(opploc)
        given_city = get_addr_field(opploc, "city")
        given_county = ''
        given_state = get_addr_field(opploc, "region")
        given_zip = get_addr_field(opploc, "postalCode")
        given_country = get_addr_field(opploc, "country")

        city, county, state, zip, country = get_revgeo_fields(lat, lng, given_city, 
                              given_county, given_state, given_zip, given_country)
        statewide = ''
        if given_state and country == 'US' and not given_address and not given_city and not given_zip:
          statewide = state

        nationwide = ''
        if given_country and not given_address and not given_city and not given_zip and not given_state:
          nationwide = country

        virtual = xmlh.get_tag_val(opploc, "virtual")
        if not given_country and not given_address and not given_city and not given_zip and not given_state:
          if virtual.lower() != 'yes':
            global NOLOC
            NOLOC += 1
            title = str(get_title(opp))
            if title:
              print_progress("missing location: %s" % title)
            opp_id = xmlh.get_tag_val(opp, "volunteerOpportunityID")
            if opp_id:
              feed_report(opp_id, 'nolocation', FEED, link)
            return totrecs, ""

        loc_fields = get_loc_fields(virtual=virtual,
                                    latitude=str(float(lat)),
                                    longitude=str(float(lng)),
                                    location_string=addr,
                                    given_location=loc_str,
                                    venue_name=xmlh.get_tag_val(opploc, "name"),
                                    city = city, county = county, state = state, 
                                    zip = zip, country = country, 
                                    statewide = statewide,
                                    nationwide = nationwide)


      opp_id = compute_stable_id(opp, orgs[0], loc_str, openended, 
                                 duration, hrs_per_week, startend)
      if duplicate_opp(opp, loc_str, startend):
        #print_progress("dedup: skipping duplicate " + opp_id)
        return totrecs, ""

      # make a file indicating to us that this 
      # opp has been found in a current feed
      try:
        open(FED_DIR + opp_id, 'w').close()
      except:
        pass

      totrecs = totrecs + 1
      #if PROGRESS and totrecs % 250 == 0:
      #  print_progress(str(totrecs)+" records generated.")

      outstr_list.append(output_field("id", opp_id))
      outstr_list.append(repeated_fields)
      outstr_list.append(time_fields)
      outstr_list.append(loc_fields)
      outstr_list.append(RECORDSEP)

  for idx, outstr in enumerate(outstr_list):
    outstr_list[idx] = "".join(i for i in outstr_list[idx] if ord(i)<128)
   
  return totrecs, "".join(outstr_list)

def get_time_fields(openended, duration, hrs_per_week, event_date_range, ical_recurrence):
  """output time-related fields, e.g. for multiple times per event."""
  if openended.lower() == 'yes':
    event_date_range = "0001-01-01T00:00:00/9999-12-31T23:59:59"
    openended_bool = "True"
  else:
    openended_bool = "False"
  # 2010-02-26T16:00:00/2010-02-26T16:00:00
  match = re.search(r'T(\d\d):(\d\d):\d\d(\s*/\s*.+?T(\d\d):(\d\d):\d\d)?',
                    event_date_range)
  startstr = endstr = ""
  if match:
    if match.group(2):
      startstr = match.group(1) + match.group(2)
    else:
      pass
    if match.group(3):
      endstr = match.group(4) + match.group(5)

  time_fields = FIELDSEP + output_field("event_date_range", event_date_range)
  time_fields += FIELDSEP + output_field("startTime", startstr)
  time_fields += FIELDSEP + output_field("endTime", endstr)
  time_fields += FIELDSEP + output_field("ical_recurrence", ical_recurrence)

  time_fields += FIELDSEP + output_field("openended", openended_bool)
  time_fields += FIELDSEP + output_field("duration", duration)
  time_fields += FIELDSEP + output_field("commitmentHoursPerWeek", hrs_per_week)
  return time_fields

def get_loc_fields(virtual, location="", latitude="", longitude="", 
  given_location="", location_string="", venue_name="",
  city = "", county = "", state = "", zip = "", country = "US", statewide = "", nationwide = ""):
  """output location-related fields, e.g. for multiple locations per event."""

  loc_fields = ""
  if virtual.lower() == 'yes':
    virtual_bool = "True"
  else:
    virtual_bool = "False"

  loc_fields += FIELDSEP + output_field("virtual", virtual_bool)
  loc_fields += FIELDSEP + output_field("location", location)
  loc_fields += FIELDSEP + output_field("latitude", latitude)
  loc_fields += FIELDSEP + output_field("longitude", longitude)
  loc_fields += FIELDSEP + output_field("location_string", location_string)
  loc_fields += FIELDSEP + output_field('latlong', str(latitude) + ',' + str(longitude))
  #loc_fields += FIELDSEP + output_field("location_0_coordinate", str(latitude))
  #loc_fields += FIELDSEP + output_field("location_1_coordinate", str(longitude))
  loc_fields += FIELDSEP + output_field("given_location", given_location)
  loc_fields += FIELDSEP + output_field("venue_name", venue_name)

  L = [ {'field' : 'city', 'value': city.lower()},
        {'field' : 'county', 'value': county.lower()},
        {'field' : 'state', 'value': state.lower()},
        {'field' : 'zip', 'value': zip},
        {'field' : 'country', 'value': country.lower()},
        {'field' : 'statewide', 'value': statewide},
        {'field' : 'nationwide', 'value': nationwide},
      ]

  for d in L:
    field = d['field']
    value = d['value']
    try:
      loc_fields += FIELDSEP + output_field(field, value)
    except:
      try:
        value = value.encode('ascii', 'ignore')
        loc_fields += FIELDSEP + output_field(field, value)
        print datetime.now(), 'converted ' + field + ' to ' + value
      except:
        print datetime.now(), 'check facet count for "' + field + '"'
        loc_fields += FIELDSEP + output_field(field, field)

  return loc_fields


def get_repeated_fields(feedinfo, opp, orgs):
  """output all fields that are repeated for each time and location."""
  rsp, feed_providerName = get_feed_fields(feedinfo)
  repeated_fields = FIELDSEP + rsp
  repeated_fields += FIELDSEP + get_event_reqd_fields(opp)
  repeated_fields += FIELDSEP + get_base_other_fields(opp, orgs[0])
  repeated_fields += FIELDSEP + get_direct_mapped_fields(opp, orgs, feed_providerName)
  return repeated_fields


def output_header(feedinfo, opp, orgs):
  """fake opportunity printer, which prints the header line instead."""
  global PRINTHEAD, HEADER_ALREADY_OUTPUT
  # no matter what, only print the header once!
  if HEADER_ALREADY_OUTPUT:
    return ""
  HEADER_ALREADY_OUTPUT = True
  PRINTHEAD = True
  outstr = output_field("id", "")
  repeated_fields = get_repeated_fields(feedinfo, opp, orgs)
  time_fields = get_time_fields("", "", "", "", "")
  loc_fields = get_loc_fields(virtual="Yes")
  PRINTHEAD = False
  return outstr + repeated_fields + time_fields + loc_fields + RECORDSEP


def convert_to_footprint_xml(instr, do_fastparse, maxrecs, progress):
  """macro for parsing an FPXML string to XML then format it."""
  if do_fastparse:
    res, numorgs, numopps = parse_footprint.parse_fast(instr, maxrecs, progress)
    return res
  else:
    # slow parse
    xmldoc = parse_footprint.parse(instr, maxrecs, progress)
    return xmlh.prettyxml(xmldoc)


def convert_to_gbase_events_type(instr, shortname, fastparse, maxrecs, progress):
  """non-trivial logic for converting FPXML to google base formatting."""
  # todo: maxrecs
  global DUPS, NOLOC, EIN501, NUMORGS
  DUPS = NOLOC = EIN501 = NUMORGS = 0

  outstr = ""
  #print_progress("convert_to_gbase_events_type...", "", progress)
  if not instr:
    return '', 0, 0

  example_org = None
  known_orgs = {}
  if True: #fastparse

    numopps = 0
    feedinfo = None
    for match in re.finditer(re.compile('<FeedInfo>.+?</FeedInfo>',
                                        re.DOTALL), instr):
      #print_progress("found FeedInfo.", progress=progress)
      feedinfo = xmlh.simple_parser(match.group(0), parse_footprint.KNOWN_ELEMENTS, False)

    if not feedinfo:
      print_progress("no FeedInfo.", progress=progress)
      return "", 0, 0

    for match in re.finditer(re.compile('<Organization>.+?</Organization>',
                                        re.DOTALL), instr):
      org = xmlh.simple_parser(match.group(0), parse_footprint.KNOWN_ELEMENTS, False)
      sponsoring_org_id = xmlh.get_tag_val(org, "organizationID")
      if sponsoring_org_id:
        known_orgs[sponsoring_org_id] = org

      if example_org is None:
        example_org = org
      #if progress and len(known_orgs) % 250 == 0:
      #  print_progress(str(len(known_orgs))+" organizations seen.")

    taggers = get_taggers()
    phoneRx = re.compile(
          '[^0-9]'+ # not a number
          '([0-9]{3}[^0-9][0-9]{3}[^0-9][0-9]{4})'+ # NNN-NNN-NNNN
          '(\s*(x|ex|ext)(ension)?\s*([0-9]+))?' # opt. extension, capture 'x'
          '[^0-9]', # not a number
      re.IGNORECASE)    

    tag_count_dict = {}
    oppslist_output = []
    for oppmatch in re.finditer(re.compile(
        '<VolunteerOpportunity>.+?</VolunteerOpportunity>', re.DOTALL), instr):
      opp = xmlh.simple_parser(oppmatch.group(0), None, False)

      # extractor/guesser for contactPhone-- note that this operates
      # on the output FPXML rather than the raw input, i.e. could miss
      # some cases.  The rationale:
      #  - operating on raw inputs means writing this N times for
      #    each feed format (mostly testing...).
      #  - most providers are FPXML now, i.e. not much value.
      contactPhone = xmlh.get_tag_val(opp, "contactPhone")
      if contactPhone == "":
        # US-only
        # doesn't work for non-numbers, e.g. 1-800-VOLUNTEER
        # doesn't work with smushed numbers, e.g. 8005567629
        #print "searching for phone:" # in "+re.sub(r'\n',' ',oppchunk)
        m = re.search(phoneRx, oppmatch.group(0))
        if m:
          extractedPhone = m.group(1)
          if m.group(5):
            extractedPhone += " ext."+ m.group(5)
          newnode = opp.createElement('contactPhone')
          newnode.appendChild(opp.createTextNode(extractedPhone))
          opp.firstChild.appendChild(newnode)
          
      # extractor/guesser for contactEmail-- see notes above in phone
      contactEmail = xmlh.get_tag_val(opp, "contactEmail")
      if contactEmail == "":
        m = re.search(r'[^a-z]([a-z0-9.+!-]+@([a-z0-9-]+[.])+[a-z]+)',
                      oppmatch.group(0), re.IGNORECASE)
        if m:
          newnode = opp.createElement('contactEmail')
          newnode.appendChild(opp.createTextNode(m.group(1)))
          opp.firstChild.appendChild(newnode)
      else:
        pass

      rec = XMLRecord(opp)
      for tagger in taggers:
        rec = XMLRecord(opp)
        rec, tag_count_dict = tagger.do_tagging(rec, feedinfo, tag_count_dict, [])

      opp = rec.opp
      if not HEADER_ALREADY_OUTPUT:
        outstr = output_header(feedinfo, opp, [example_org, example_org, example_org])

      numopps, spiece = output_opportunity(opp, feedinfo, known_orgs, numopps)
      oppslist_output.append(spiece)

      if (maxrecs > 0 and numopps > maxrecs):
        break
      
    for tag, tag_count in tag_count_dict.iteritems():
      print_progress("tagged %s: %d" % (tag, tag_count))

    outstr += "".join(oppslist_output)

  NUMORGS = len(known_orgs)
  print_progress("no location: " + str(NOLOC))
  print_progress(" duplicates: " + str(DUPS))
  print_progress("    501(c)3: " + str(EIN501))
  print_progress("parsed opps: " + str(numopps))

  if FEED:
    fh = open(FEEDSDIR + '/' + FEED + '-last.txt', 'w')
    if fh:
      fh.write('numorgs\t' + str(NUMORGS) + '\n')
      fh.write('noloc\t' + str(NOLOC) + '\n')
      fh.write('dups\t' + str(DUPS) + '\n')
      fh.write('ein501c3\t' + str(EIN501) + '\n')
      fh.close()

  return outstr, len(known_orgs), numopps


def guess_shortname(filename):
  """from the input filename, guess which feed this is."""
  global IGNORE_DUPLICATES
  IGNORE_DUPLICATES = False
  if re.search("handsonnetwork1800", filename):
    return "handsonnetwork1800"

  if re.search("handsonnetworktechnologies", filename):
    return "handsonnetworktechnologies"

  if re.search("handsonnetworkconnect", filename):
    IGNORE_DUPLICATES = True
    return "handsonnetworkconnect"

  if re.search("updateHON", filename):
    IGNORE_DUPLICATES = True
    return "handsonnetworkconnect"

  # could comment out legacy HON feed 10/12/2011
  # Commented 1/23/13
  # if re.search("(handson|hot.footprint)", filename):
  #  return "handsonnetwork"

  # added daytabank 10/12/2011
  if re.search("daytabank", filename):
    return "daytabank"
	
  if re.search("spreadsheets[.]google[.]com", filename):
    return "gspreadsheet"
  if filename.find('oppsfeed') >= 0:
    return "gspreadsheet"
  if re.search(r'onlinespreadsheet', filename):
    return "onlinespreadsheet"

  if re.search(r'rockthevote', filename):
    return "rockthevote"
  if re.search(r'sparked', filename):
    return "sparked"
  if re.search(r'diy', filename):
    return "diy"
  if re.search(r'350org', filename):
    return "350org"
  if re.search(r'1sky', filename):
    return "1sky"
  if re.search("usa-?service", filename):
    return "usaservice"
  if re.search(r'meetup', filename):
    return "meetup"
  if re.search(r'barackobama', filename):
    return "mybarackobama"
  if re.search(r'united.*way', filename):
    return "unitedway"
  if re.search(r'americanredcross', filename):
    return "americanredcross"
  if re.search(r'aarp', filename):
    return "aarp"
  if re.search(r'greentheblock', filename):
    return "greentheblock"
  if re.search(r'citizencorps', filename):
    return "citizencorps"
  if re.search(r'samaritan', filename):
    return "samaritan"
  if re.search(r'catchafire', filename):
    return "catchafire"
  if re.search(r'getinvolved', filename):
    return "getinvolved"
  if re.search(r'ymca', filename):
    return "ymca"
  if re.search(r'uso', filename):
    return "uso"
  if re.search(r'usaintlexp', filename):
    return "usaintlexp"
  if re.search(r'samaritan', filename):
    return "samaritan"
  if re.search(r'newyorkcares', filename):
    return "newyorkcares"
  if re.search(r'911dayofservice', filename):
    return "911dayofservice"
  if re.search(r'universalgiving', filename):
    return "universalgiving"
  if re.search(r'washoe', filename):
    return "washoecounty"
  if re.search("habitat", filename):
    return "habitat"
  if re.search("americansolutions", filename):
    return "americansolutions"
  if re.search("(volunteer[.]?gov)", filename):
    return "volunteergov"
  if re.search("(whichoneis.com|beextra|extraordinari)", filename):
    return "extraordinaries"
  if re.search("idealist", filename):
    return "idealist"
  if re.search("(userpostings|/export/Posting)", filename):
    return "footprint_userpostings"
  if re.search("craigslist", filename):
    return "craigslist"
  if re.search("americorps", filename):
    return "americorps"
  if re.search("givingdupage", filename):
    return "givingdupage"
  if re.search("mlk(_|day)", filename):
    return "mlk_day"
  if re.search("servenet", filename):
    return "servenet"
  if re.search("servicenation", filename):
    return "servicenation"
  if re.search(r'(seniorcorps|985148b9e3c5b9523ed96c33de482e3d)', filename):
    # note: has to come before volunteermatch
    return "seniorcorps"
  if re.search(r'(volunteermatch|cfef12bf527d2ec1acccba6c4c159687)', filename):
    return "volunteermatch"
  if re.search(r"vm-20101027", filename):
    return "volunteermatch"
  if re.search(r'vm-nat', filename):
    return "vm-nat"
  if re.search("christianvol", filename):
    return "christianvolunteering"
  if re.search("volunteer(two|2)", filename):
    return "volunteertwo"
  if re.search("up2us", filename):
    return "up2us"
  if re.search("mentorpro", filename):
    return "mentorpro"
  if re.search(r'(mpsg_feed|myproj_servegov)', filename):
    return "myproj_servegov"
  return ""

def guess_parse_func(inputfmt, filename, feed_providername):
  """from the filename and the --inputfmt,guess the input type and parse func"""

  # for development
  if inputfmt == "fpxml":
    return "fpxml", parse_footprint.parse_fast

  shortname = guess_shortname(filename)
  #print 'guessed ' + shortname

  # FPXML providers
  fp = parse_footprint
  """"
  LEGACY HON feeds Commented out on 1/23/2013
  if shortname == "handsonnetwork1800":
    return "fpxml", fp.parser(
      '500', 'handsonnetwork1800', 'handsonnetwork1800', 'http://handsonnetwork.org/',
      'HandsOn Network')

  if shortname == "handsonnetworktechnologies":
    return "fpxml", fp.parser(
      '501', 'handsonnetworktechnologies', 'handsonnetworktechnologies', 'http://handsonnetwork.org/',
      'HandsOn Network')
  """
  if shortname == "handsonnetworkconnect":
    return "fpxml", fp.parser(
      '502', 'handsonnetworkconnect', 'handsonnetworkconnect', 'http://handsonnetwork.org/',
      'HandsOn Network')

  # added daytabank 10/12/2011
  if shortname == "daytabank":
    return "fpxml", fp.parser(
      '503', 'daytabank', 'daytabank', 'http://daytabank.handsonnetwork.org/',
      'Make a Difference Day')

  """Commented on 1/23/2013
  # can comment out legacy HON feed 10/12/2011
  if shortname == "handsonnetwork":
    return "fpxml", fp.parser(
      '102', 'handsonnetwork', 'handsonnetwork', 'http://handsonnetwork.org/',
      'HandsOn Network')
      """

  if shortname == "volunteermatch" or shortname == "vm-20101027":
    return "fpxml", fp.parser(
      '104', 'volunteermatch', 'volunteermatch',
      'http://www.volunteermatch.org/', 'Volunteer Match')
  if shortname == "vm-nat":
    return "fpxml", fp.parser(
      '104', 'vm-nat', 'vm-nat', 
      'http://www.volunteermatch.org/', 'Volunteer Match')
  if shortname == "volunteergov":
    return "fpxml", fp.parser(
      '107', 'volunteergov', 'volunteergov', 'http://www.volunteer.gov/',
      'volunteer.gov')
  if shortname == "extraordinaries":
    return "fpxml", fp.parser(
      '110', 'extraordinaries', 'extraordinaries', 'http://www.beextra.org/',
      'The Extraordinaries')
  if shortname == "meetup":
    return "fpxml", fp.parser(
      '112', 'meetup', 'meetup', 'http://www.meetup.com/',
      'Meetup')
  if shortname == "americansolutions":
    return "fpxml", fp.parser(
      '115', 'americansolutions', 'americansolutions',
      'http://www.americansolutions.com/',
      'American Solutions for Winning the Future')
  if shortname == "mybarackobama":
    return "fpxml", fp.parser(
      '116', 'mybarackobama', 'mybarackobama', 'http://my.barackobama.com/',
      'Organizing for America / DNC')
  if shortname == "unitedway":
    return "fpxml", fp.parser(
      '122', 'unitedway', 'unitedway', 'http://www.unitedway.org/',
      'United Way')
  if shortname == "americanredcross":
    return "fpxml", fp.parser(
      '123', 'americanredcross', 'americanredcross', 'http://www.givelife.org/',
      'American Red Cross')
  if shortname == "citizencorps":
    return "fpxml", fp.parser(
      '124', 'citizencorps', 'citizencorps', 'http://citizencorps.gov/',
      'Citizen Corps / FEMA')
  if shortname == "ymca":
    return "fpxml", fp.parser(
      '126', 'ymca', 'ymca', 'http://www.ymca.net/',
      'YMCA')
  if shortname == "catchafire":
    return "fpxml", fp.parser(
      '138', 'catchafire', 'catchafire', 'http://catchafire.org/',
      'CatchAFire')
  if shortname == "aarp":
    return "fpxml", fp.parser(
      '127', 'aarp', 'aarp', 'http://www.aarp.org/',
      'AARP')
  if shortname == "greentheblock":
    return "fpxml", fp.parser(
      '128', 'greentheblock', 'greentheblock', 'http://greentheblock.net/',
      'Green the Block')
  if shortname == "washoecounty":
    return "fpxml", fp.parser(
      '129', 'washoecounty', 'washoecounty', 'http://www.washoecounty.us/',
      'Washoe County, Nevada')
  if shortname == "universalgiving":
    return "fpxml", fp.parser(
      '130', 'universalgiving', 'universalgiving',
      'http://www.universalgiving.org/', 'Universal Giving')
  if shortname == "911dayofservice":
    return "fpxml", fp.parser(
      '131', '911dayofservice', '911dayofservice', 'http://www.911dayofservice.org/',
      'National Day of Service and Remembrance')
  if shortname == "newyorkcares":
    return "fpxml", fp.parser(
      '132', 'newyorkcares', 'newyorkcares', 'http://www.newyorkcares.org/',
      'New York Cares')
  if shortname == "servicenation":
    return "fpxml", fp.parser(
      '133', 'servicenation', 'servicenation', 'http://www.servicenation.org/',
      'Service Nation')
  if shortname == "samaritan":
    return "fpxml", fp.parser(
      '134', 'samaritan', 'samaritan', 'http://www.samaritan.com',
      'Samaritan')
  if shortname == "1sky":
    return "fpxml", fp.parser(
      '135', '1sky', '1sky', 'http://1sky.org/',
      '1Sky')
  if shortname == "rockthevote":
    return "fpxml", fp.parser(
      '136', 'rockthevote', 'rockthevote', 'http://rockthevote.com/',
      'rockthevote')
  if shortname == "up2us":
    return "fpxml", fp.parser(
      '137', 'up2us', 'up2us', 'http://www.civicore.com/',
      'civicore')
  if shortname == "usaintlexp":
    return "fpxml", fp.parser(
      '139', 'usaintlexp', 'usaintlexp', 'http://usa.international-experience.net/',
      'usaintlexp')
  if shortname == "samaritan":
    return "fpxml", fp.parser(
      '140', 'samaritan', 'samaritan', 'http://ec.volunteernow.com/',
      'samaritan')
  if shortname == "uso":
    return "fpxml", fp.parser(
      '141', 'USO', 'USO', 'http://www.usovolunteer.org/',
      'USO')
  if shortname == "getinvolved":
    return "fpxml", fp.parser(
      '142', 'getinvolved', 'getinvolved', 'http://www.getinvolved.ca/',
      'getinvolved')

  if shortname == "onlinespreadsheet":
    if not feed_providername:
      feed_providername = "6000"

    return "fpxml", fp.parser(
      '6000', feed_providername, feed_providername, 'http://www.allforgood.org/',
      'AfG')
  #are they VETTED? check to see if we need to add the new feed to list of Vetted feeds in taggers.py 

  if shortname == "habitat":
    parser = fp.parser(
      '111', 'habitat', 'habitat',
      'http://www.habitat.org/', 'Habitat for Humanity')
    def parse_habitat(instr, maxrecs, progress):
      # fixup bad escaping
      newstr = re.sub(r'&code=', '&amp;code=', instr)
      return parser(newstr, maxrecs, progress)
    return "habitat", parse_habitat

  # networkforgood providers
  nfg = parse_networkforgood
  if shortname == "americorps":
    return "nfg", nfg.parser(
      '106', 'americorps', 'americorps', 'http://www.americorps.gov/',
      'AmeriCorps')
  if shortname == "servenet":
    return "nfg", nfg.parser(
      '114', 'servenet', 'servenet', 'http://www.servenet.org/',
      'servenet')
  if shortname == "mlk_day":
    return "nfg", nfg.parser(
      '115', 'mlk_day', 'mlk_day', 'http://my.mlkday.gov/',
      'Martin Luther King day')
  if shortname == "christianvolunteering":
    return "nfg", nfg.parser(
      '117', 'christianvolunteering', 'christianvolunteering',
      'http://www.christianvolunteering.org/', 'Christian Volunteering')
  if shortname == "volunteertwo":
    return "nfg", nfg.parser(
      '118', 'volunteer2', 'volunteer2',
      'http://www.volunteer2.com/', 'Volunteer2')
  if shortname == "mentorpro":
    return "nfg", nfg.parser(
      '119', 'mentor', 'mentor',
      'http://www.mentorpro.org/', 'MENTOR')
  if shortname == "myproj_servegov":
    return "nfg", nfg.parser(
      '120', 'myproj_servegov', 'myproj_servegov',
      'http://myproject.serve.gov/', 'MyprojectServeGov')
  if shortname == "seniorcorps":
    return "nfg", nfg.parser(
      '121', 'seniorcorps', 'seniorcorps',
      'http://www.seniorcorps.gov/', 'SeniorCorps')
  if shortname == "givingdupage":
    return "nfg", nfg.parser(
      '125', 'givingdupage', 'givingdupage', 'http://www.dupageco.org/',
      'Giving Dupage')

  # custom formats
  if shortname == "gspreadsheet":
    return "gspreadsheet", gsp.parse

  if shortname == "usaservice" or shortname == "usasvc":
    return "usaservice", parse_usaservice.parse

  if shortname == "craigslist" or shortname == "cl":
    return "craigslist", parse_craigslist.parse

  if shortname == "sparked":
    return "sparked", parse_sparked.parse

  if shortname == "diy":
    return "diy", parse_diy.parse

  if shortname == "350org":
    return "350org", parse_350org.parse

  if shortname == "idealist":
    return "idealist", parse_idealist.parse

  print datetime.now(), "couldn't guess input format-- try --inputfmt"
  sys.exit(1)


def clean_input_string(instr):
  """run various cleanups for low-level encoding issues."""
  def cleaning_progress(msg):
    """macro"""
    if DEBUG:
      print_progress(msg+": "+str(len(instr))+" bytes.")

  cleaning_progress("read file")
  instr = re.sub(r'\r\n?', "\n", instr)
  cleaning_progress("filtered DOS newlines")
  instr = re.sub(r'(?:\t|&#9;)', " ", instr)
  cleaning_progress("filtered tabs")
  instr = re.sub(r'\xc2?[\x93\x94\222]', "'", instr)
  cleaning_progress("filtered iso8859-1 single quotes")
  instr = re.sub(r'\xc2?[\223\224]', '"', instr)
  cleaning_progress("filtered iso8859-1 double quotes")
  instr = re.sub(r'\xc2?[\225\226\227]', "-", instr)
  cleaning_progress("filtered iso8859-1 dashes")
  instr = xmlh.clean_string(instr)
  cleaning_progress("filtered nonprintables")
  return instr

def parse_options():
  """parse cmdline options"""
  global DEBUG, PROGRESS, FIELDSEP, RECORDSEP, OUTPUTFMT
  parser = OptionParser("usage: %prog [options] sample_data.xml ...")
  parser.set_defaults(geocode_debug=False)
  parser.set_defaults(debug=False)
  parser.set_defaults(abridged=False)
  parser.set_defaults(progress=False)
  parser.set_defaults(debug_input=False)
  parser.set_defaults(outputfmt="basetsv")
  parser.set_defaults(output="")
  parser.set_defaults(compress_output=False)
  parser.set_defaults(test=False)
  parser.set_defaults(clean=True)
  parser.set_defaults(maxrecs=-1)
  parser.add_option("-d", "--dbg", action="store_true", dest="debug")
  parser.add_option("--abridged", action="store_true", dest="abridged")
  parser.add_option("--noabridged", action="store_false", dest="abridged")
  parser.add_option("--clean", action="store_true", dest="clean")
  parser.add_option("--noclean", action="store_false", dest="clean")
  parser.add_option("--inputfmt", action="store", dest="inputfmt")
  parser.add_option("--test", action="store_true", dest="test")
  parser.add_option("--dbginput", action="store_true", dest="debug_input")
  parser.add_option("--progress", action="store_true", dest="progress")
  parser.add_option("--outputfmt", action="store", dest="outputfmt")
  parser.add_option("--output", action="store", dest="output")
  parser.add_option("--compress_output", action="store_true",
                    dest="compress_output")
  parser.add_option("--nocompress_output", action="store_false",
                    dest="compress_output")
  parser.add_option("-g", "--geodbg", action="store_true", dest="geocode_debug")
  parser.add_option("--ftpinfo", dest="ftpinfo")
  parser.add_option("--fs", "--fieldsep", action="store", dest="fs")
  parser.add_option("--rs", "--recordsep", action="store", dest="rs")
  parser.add_option("-n", "--maxrecords", action="store", dest="maxrecs")
  parser.add_option("--feed_providername", action="store", dest="feed_providername")
  (options, args) = parser.parse_args(sys.argv[1:])
  if (len(args) == 0):
    parser.print_help()
    sys.exit(0)

  if options.fs != None:
    FIELDSEP = options.fs
  if options.rs != None:
    RECORDSEP = options.rs
  if (options.debug):
    DEBUG = True
    geocoder.GEOCODE_DEBUG = True
    PROGRESS = True
    geocoder.SHOW_PROGRESS = True
    FIELDSEP = "\n"
  if (options.geocode_debug):
    geocoder.GEOCODE_DEBUG = True
  if options.test:
    options.progress = True
  if (options.progress):
    PROGRESS = True
    geocoder.SHOW_PROGRESS = True
  if options.ftpinfo and not options.outputfmt:
    options.outputfmt = "basetsv"
  OUTPUTFMT = options.outputfmt
  return options, args

def open_input_filename(filename):
  """handle different file/URL opening methods."""
  if re.search(r'^https?://', filename):
    print_progress("starting download of "+filename)
    try:
      outfh = urllib2.urlopen(filename)
    except:
      outfh = None

    if outfh is not None and (re.search(r'[.]gz$', filename)):
      # is there a way to fetch and unzip an URL in one shot?
      print_progress("ah, gzip format.")
      content = outfh.read()
      outfh.close()
      print_progress("download done.")
      tmp_fn = "/tmp/tmp-"+hashlib.md5().hexdigest()
      tmpfh = open(tmp_fn, "wb+")
      tmpfh.write(content)
      tmpfh.close()
      outfh = gzip.open(tmp_fn, 'rb')
    return outfh
  elif re.search(r'[.]gz$', filename):
    return gzip.open(filename, 'rb')
  elif filename == "-":
    return sys.stdin
  return open(filename, 'rb')

def test_parse(footprint_xmlstr, maxrecs):
  """run the data through and then re-parse the output."""
  print datetime.now(), "testing input: generating Footprint XML..."
  fpxml = convert_to_footprint_xml(footprint_xmlstr, True, int(maxrecs), True)
                                   
  # free some RAM
  del footprint_xmlstr
  print datetime.now(), "testing input: parsing and regenerating FPXML..."
  fpxml2 = convert_to_footprint_xml(fpxml, True, int(maxrecs), True)
  print datetime.now(), "testing input: comparing outputs..."
  hash1 = hashlib.md5(fpxml).hexdigest()
  hash2 = hashlib.md5(fpxml2).hexdigest()
  fn1 = "/tmp/pydiff-"+hash1
  fn2 = "/tmp/pydiff-"+hash2
  if hash1 == hash2:
    print datetime.now(), "success:  getting head...\n"
    outfh = open(fn1, "w+")
    outfh.write(fpxml)
    outfh.close()
    subprocess.call(['head', fn1])
  else:
    print datetime.now(), "errors-- hash1=" + hash1 + " hash2=" + \
        hash2 + " running diff", fn1, fn2
    outfh = open(fn1, "w+")
    outfh.write(fpxml)
    outfh.close()
    outfh = open(fn2, "w+")
    outfh.write(fpxml2)
    outfh.close()
    subprocess.call(['diff', fn1, fn2])
    # grr-- difflib performance sucks
    #for line in difflib.unified_diff(fpxml, fpxml2, \
    #  fromfile='(first output)', tofile='(second output)'):
    #print line


def process_file(filename, options, providerName="", providerID="", feedID="", providerURL=""):
  global FEED

  shortname = guess_shortname(filename)
  FEED = shortname

  inputfmt, parsefunc = guess_parse_func(options.inputfmt, filename, options.feed_providername)

  try:
    infh = open_input_filename(filename)
  except:
    print_progress("could not open %s" % filename)
    return 0, 0, 0, ""
  if infh is None:
    return 0, 0, 0, ""

  print_progress("reading data...")
  # don't put this inside open_input_filename() because it could be large
  instr = infh.read()
  print_progress("done reading data.")

  # remove bad encodings etc.
  if options.clean:
    #print_progress("cleaning input.")
    instr = clean_input_string(instr)

  # split nasty XML inputs, to help isolate problems
  if options.debug_input:
    instr = re.sub(r'><', r'>\n<', instr)

  #print_progress("inputfmt: "+inputfmt)
  #print_progress("outputfmt: "+options.outputfmt)
  print_progress("input data: "+str(len(instr))+" bytes", shortname)

  print_progress("parsing...")
  footprint_xmlstr, numorgs, numopps = \
      parsefunc(instr, int(options.maxrecs), PROGRESS)

  if (providerID != "" and
      footprint_xmlstr.find('<providerID></providerID>')):
    footprint_xmlstr = re.sub(
      '<providerID></providerID>',
      '<providerID>%s</providerID>' % providerID, footprint_xmlstr)
  if (providerName != "" and
      footprint_xmlstr.find('<providerName></providerName>')):
    footprint_xmlstr = re.sub(
      '<providerName></providerName>',
      '<providerName>%s</providerName>' % providerName, footprint_xmlstr)
  if (providerID != "" and
      footprint_xmlstr.find('<feedID></feedID>')):
    footprint_xmlstr = re.sub(
      '<feedID></feedID>',
      '<feedID>%s</feedID>' % feedID, footprint_xmlstr)
  if (providerURL != "" and
      footprint_xmlstr.find('<providerURL></providerURL>')):
    footprint_xmlstr = re.sub(
      '<providerURL></providerURL>',
      '<providerURL><![CDATA[%s]]></providerURL>' % providerURL, footprint_xmlstr)

  if options.test:
    # free some RAM
    del instr
    test_parse(footprint_xmlstr, options.maxrecs)
    print "exiting because of options.test"
    sys.exit(0)


  fastparse = not options.debug_input
  if OUTPUTFMT == "fpxml":
    print convert_to_footprint_xml(footprint_xmlstr, fastparse,
                                   int(options.maxrecs), PROGRESS)
    print "exiting because outputfmt = fpxml"
    sys.exit(0)

  if OUTPUTFMT != "basetsv":
    print >> sys.stderr, datetime.now(), \
        "--outputfmt not implemented: try 'basetsv','fpbasetsv' or 'fpxml'"
    sys.exit(1)

  maxrecs = int(options.maxrecs)
  maxrecs = 0

  outstr, numorgs, numopps = convert_to_gbase_events_type(
    footprint_xmlstr, shortname, fastparse, maxrecs, PROGRESS)
   
  ln = 0
  if footprint_xmlstr:
    ln = len(footprint_xmlstr)

  return ln, numorgs, numopps, outstr

def main():
  """main function for cmdline execution."""
  start_time = datetime.now()
  options, args = parse_options()
  filename = args[0]
  if not re.search("spreadsheets[.]google[.]com", filename):
    bytes, numorgs, numopps, outstr = process_file(filename, options)
  else:
     # spreadsheets only
    if OUTPUTFMT == "fpxml":
      gsp.parser_error("FPXML format not supported for "+
                       "spreadsheet-of-spreadsheets")
      sys.exit(1)
      
    bytes = numorgs = numopps = 0
    outstr = ""
    """
    # This was the old sheet 
    # Commmented out on 1/25/2013
    
    match = re.search(r'key=([^& ]+)', filename)
    url = "http://spreadsheets.google.com/feeds/cells/" + match.group(1)
    url += "/1/public/basic"

    data = {}
    updated = {}
    print "================================================== PUBLIC SPREADSHEETS"
    print "processing master spreadsheet", url
    maxrow, maxcol = gsp.read_gspreadsheet(url, data, updated, PROGRESS)
    header_row, header_startcol = gsp.find_header_row(data, 'provider name')

    # check to see if there's a header-description row
    header_desc = gsp.cellval(data, header_row+1, header_startcol)
    if not header_desc:
      gsp.parser_error("blank row not allowed below header row")
    else:

      header_desc = header_desc.lower()
      data_startrow = header_row + 1
      if header_desc.find("example") >= 0:
        data_startrow += 1

      bytes = numorgs = numopps = 0
      outstr = ""
      for row in range(data_startrow, int(maxrow)+1):
        providerName = gsp.cellval(data, row, header_startcol)
        if providerName is None or providerName == "":
          print "missing provider name from row "+str(row)
          continue
        providerID = gsp.cellval(data, row, header_startcol+1)
        if providerID is None or providerID == "":
          print "missing provider ID from row "+str(row)
          continue
        providerURL = gsp.cellval(data, row, header_startcol+2)
        if providerURL is None or providerURL == "":
          print "missing provider URL from row "+str(row)
          continue

        match = re.search(r'key=([^& ]+)', providerURL)
        providerURL = "http://spreadsheets.google.com/feeds/cells/"
        providerURL += match.group(1)
        providerURL += "/1/public/basic"
  
        feedID = re.sub(r'[^a-z]', '', providerName.lower())[0:24]
        if len(feedID) < 1:
          feedID = providerName

        print "processing spreadsheet", providerURL, "named", providerName, " - feedID", feedID

        providerBytes, providerNumorgs, providerNumopps, tmpstr = process_file(
          providerURL, options, providerName, providerID, feedID, providerURL)

        print "done processing spreadsheet: name="+providerName, \
              "feedID="+feedID, "records="+str(providerNumopps), \
              "url="+providerURL

        bytes += providerBytes
        numorgs += providerNumorgs
        numopps += providerNumopps
        outstr += tmpstr
    """
    # added week of April 16th, 2012 
    # Processes all sheets submitted via the google form.
    # These sheets are preprocessed by /spredsheets/run.php
    # run.php generates process.py which is an array of sheets 
    print "================================================== PRIVATE SPREADSHEETS"
    for sheet in sheet_list:
      providerURL = 'http://staging.servicefootprint.appspot.com/oppsfeed?id=' + sheet['id']
      providerURL += '&r=' + str(random.random())

      providerBytes, providerNumorgs, providerNumopps, tmpstr = process_file(
        providerURL, options, sheet['pid'], sheet['pid'], sheet['pid'], providerURL)

      bytes += providerBytes
      numorgs += providerNumorgs
      numopps += providerNumopps
      outstr += tmpstr

  #only need this if Base quoted fields it enabled
  #outstr = re.sub(r'"', r'&quot;', outstr)
  if (options.ftpinfo):
    ftp_to_base(filename, options.ftpinfo, outstr)
  elif options.output == "":
    print outstr,
  elif options.compress_output:
    gzip_fh = gzip.open(options.output, 'wb', 9)
    gzip_fh.write(outstr)
    gzip_fh.close()
  else:
    outfh = open(options.output, "w")
    outfh.write(outstr)
    outfh.close()


if __name__ == "__main__":
  main()
