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
import gzip
import hashlib
import urllib
import re
from csv import DictReader, DictWriter, excel_tab, register_dialect, QUOTE_NONE
from datetime import datetime
import geocoder
import parse_footprint
import parse_gspreadsheet as pgs
import parse_usaservice
import parse_networkforgood
import parse_idealist
import parse_craigslist
import parse_volunteermatch
import subprocess
import sys
import time
import xml_helpers as xmlh
from optparse import OptionParser

import dateutil
import dateutil.tz
import dateutil.parser

FIELDSEP = "\t"
RECORDSEP = "\n"

MAX_ABSTRACT_LEN = 300

DEBUG = False
PROGRESS = False
PRINTHEAD = False
ABRIDGED = False
OUTPUTFMT = "fpxml"

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

#BASE_PUB_URL = "http://change.gov/"
BASE_PUB_URL = "http://adamsah.net/"

SEARCHFIELDS = {
  # required
  "description":"builtin",
  "event_date_range":"builtin",
  "link":"builtin",
  "location":"builtin",
  "title":"builtin",
  # needed for search restricts
  "latitude":"float",
  "longitude":"float",
  # needed for query by time-of-day
  "startTime":"integer",
  "endTime":"integer",
  # needed for basic search results
  "id":"builtin",
  "detailURL":"URL",
  "abstract":"string",
  "location_string":"string",
  "feed_providerName":"string",
}  

FIELDTYPES = {
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
  "minimumAge":"integer",
  "startTime":"integer",
  "endTime":"integer",

  "latitude":"float",
  "longitude":"float",

  "providerURL":"URL",
  "detailURL":"URL",
  "org_organizationURL":"URL",
  "org_logoURL":"URL",
  "org_providerURL":"URL",
  "feed_providerURL":"URL",

  "lastUpdated":"dateTime",
  "expires":"dateTime",
  "feed_createdDateTime":"dateTime",

  # note: type "location" isn"t safe because the Base geocoder can fail,
  # causing the record to be rejected
  "duration":"string",
  "abstract":"string",
  "sexRestrictedTo":"string",
  "skills":"string",
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
  "categories":"string",
  "audiences":"string",
  "commitmentHoursPerWeek":"string",
  "employer":"string",
  "feed_providerName":"string",
  "feed_description":"string",
  "providerID":"string",
  "feed_providerID":"string",
  "feedID":"string",
  "opportunityID":"string",
  "organizationID":"string",
  "sponsoringOrganizationID":"strng",
  "volunteerHubOrganizationID":"string",
  "org_nationalEIN":"string",
  "org_guidestarID":"string",
  "venue_name":"string",
  "location_string":"string",
  "orgLocation":"string",
}

class our_dialect(excel_tab):
  quotechar = ''
  quoting = QUOTE_NONE
register_dialect('our-dialect', our_dialect)

def print_progress(msg, filename="", progress=None):
  """print progress indicator."""
  # not allowed to say progress=PROGRESS as a default arg
  if progress == None:
    progress = PROGRESS
  xmlh.print_progress(msg, filename, progress=progress)

def print_status(msg, filename="", progress=None):
  """print status indicator, for stats collection."""
  if progress == None:
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
  try:
    tzinfo = dateutil.tz.tzstr(timezone)
  except:
    tzinfo = dateutil.tz.tzutc()
  try:
    timestr = dateutil.parser.parse(datestr + " " + timestr)
  except:
    print "error parsing datetime: "+datestr+" "+timestr
    return ""
  timestr = timestr.replace(tzinfo=tzinfo)
  pst = dateutil.tz.tzstr("PST8PDT")
  timestr = timestr.astimezone(pst)
  if timestr.year < 1900:
    timestr = timestr.replace(year=timestr.year+1900)
  res = timestr.strftime("%Y-%m-%dT%H:%M:%S")
  res = re.sub(r'Z$', '', res)
  return res

CSV_REPEATED_FIELDS = ['categories', 'audiences']
DIRECT_MAP_FIELDS = [
  'opportunityID', 'organizationID', 'volunteersSlots', 'volunteersFilled',
  'volunteersNeeded', 'minimumAge', 'sexRestrictedTo', 'skills', 'contactName',
  'contactPhone', 'contactEmail', 'providerURL', 'language', 'lastUpdated',
  'expires']
ORGANIZATION_FIELDS = [
  'nationalEIN', 'guidestarID', 'name', 'missionStatement', 'description',
  'phone', 'fax', 'email', 'organizationURL', 'logoURL', 'providerURL']

def flattener_value(node):
  """return a DOM node's first child, sans commas"""
  if (node.firstChild != None):
    return node.firstChild.data.replace(",", "")
  else:
    return ""

def flatten_to_csv(domnode):
  """prints the children of a DOM node as CSV separated strings"""
  # pylint: disable-msg=W0141
  return ",".join(filter(lambda x: x != "",
                         map(flattener_value, domnode.childNodes)))


def output_field(name, value):
  """print a field value, handling long strings, header lines and
  custom datatypes."""
  #global PRINTHEAD, DEBUG
  if PRINTHEAD:
    if name not in FIELDTYPES:
      print datetime.now(), "no type for field: " + name + FIELDTYPES[name]
      sys.exit(1)
    elif FIELDTYPES[name] == "builtin":
      return name
    elif OUTPUTFMT == "basetsv":
      return "c:"+name+":"+FIELDTYPES[name]
    else:
      return name+":"+FIELDTYPES[name]

  # common fixup for URL fields
  if re.search(r'url', name, re.IGNORECASE):
    # common error in datafeeds: http:///
    value = re.sub(r'http:///', 'http://', value)
    if value != "" and not re.search(r'^https?://', value):
      # common error in datafeeds: missing leading http://
      value = "http://" + value
    # common error in datafeeds: http://http://
    value = re.sub(r'http://http://', 'http://', value)

  if OUTPUTFMT == "basetsv":
    # grr: Base tries to treat commas in custom fields as being lists ?!
    # http://groups.google.com/group/base-help-basics/browse_thread/thread/
    #   c4f51447191a6741
    # TODO: note that this may cause fields to expand beyond their maxlen
    # (e.g. abstract)
    value = re.sub(r',', ';;', value)
  if DEBUG:
    if (len(value) > 70):
      value = value[0:67] + "... (" + str(len(value)) + " bytes)"
    return name.rjust(22) + " : " + value
  if (FIELDTYPES[name] == "dateTime"):
    return convert_dt_to_gbase(value, "", "UTC")
  return value

def get_addr_field(node, field):
  """assuming a node is named (field), return it with optional trailing spc."""
  addr = xmlh.get_tag_val(node, field)
  if addr != "":
    addr += " "
  return addr

def get_city_addr_str(node):
  """synthesize a city-region-postal-country string."""
  # note: avoid commas, so it works with CSV
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

def compute_stable_id(opp, org, locstr, openended, duration,
                      hrs_per_week, startend):
  """core algorithm for computing an opportunity's unique id."""
  if DEBUG:
    print "opp=" + str(opp)  # shuts up pylint
  eid = xmlh.get_tag_val(org, "nationalEIN")
  if (eid == ""):
    # support informal "organizations" that lack EINs
    eid = xmlh.get_tag_val(org, "organizationURL")
  # TODO: if two providers have same listing, good odds the
  # locations will be slightly different...
  loc = locstr

  # TODO: if two providers have same listing, the time info
  # is unlikely to be exactly the same, incl. missing fields
  timestr = openended + duration + hrs_per_week + startend
  title = get_title(opp)
  abstract = get_abstract(opp)
  detailURL = xmlh.get_tag_val(opp, 'detailURL')
  hashstr = "\t".join([eid, loc, timestr, title, abstract, detailURL])
  return hashlib.md5(hashstr).hexdigest()

def get_abstract(opp):
  """process abstract-- shorten, strip newlines and formatting.
  TODO: cache/memoize this."""
  abstract = xmlh.get_tag_val(opp, "abstract")
  if abstract == "":
    abstract = xmlh.get_tag_val(opp, "description")
  abstract = cleanse_snippet(abstract)
  return abstract[:MAX_ABSTRACT_LEN]

def get_direct_mapped_fields(opp, org):
  """map a field directly from FPXML to Google Base."""
  outstr = output_field("abstract", get_abstract(opp))
  if ABRIDGED:
    return outstr

  paid = xmlh.get_tag_val(opp, "paid")
  if (paid == "" or paid.lower()[0] != "y"):
    paid = "n"
  else:
    paid = "y"
  outstr += FIELDSEP + output_field("paid", paid)
  detailURL = xmlh.get_tag_val(opp, "detailURL")
  outstr += FIELDSEP + output_field("detailURL", detailURL)
  for field in DIRECT_MAP_FIELDS:
    outstr += FIELDSEP + output_tag_value(opp, field)
  for field in ORGANIZATION_FIELDS:
    outstr += FIELDSEP + output_field("org_"+field,
                                      xmlh.get_tag_val(org, field))
  for field in CSV_REPEATED_FIELDS:
    outstr += FIELDSEP
    fieldval = opp.getElementsByTagName(field)
    val = ""
    if (fieldval.length > 0):
      val = flatten_to_csv(fieldval[0])
    outstr += output_field(field, val)

  # orgLocation
  outstr += FIELDSEP
  fieldval = opp.getElementsByTagName("orgLocation")
  if (fieldval.length > 0):
    outstr += output_loc_field(fieldval[0], "orgLocation")
  else:
    outstr += output_field("orgLocation", "")

  return outstr

def get_base_other_fields(opp, org):
  """These are fields that exist in other Base schemas-- for the sake of
  possible syndication, we try to make ourselves look like other Base
  feeds.  Since we're talking about a small overlap, these fields are
  populated *as well as* direct mapping of the footprint XML fields."""
  outstr = output_field("employer", xmlh.get_tag_val(org, "name"))
  if ABRIDGED:
    return outstr
  outstr += FIELDSEP + output_field("quantity",
                         xmlh.get_tag_val(opp, "volunteersNeeded"))
  outstr += FIELDSEP + output_field("image_link",
                                    xmlh.get_tag_val(org, "logoURL"))
  # don't map expiration_date -- Base has strict limits (e.g. 2 weeks)
  return outstr


sent_start_rx = re.compile(r'((^\s*|[.]\s+)[A-Z])([A-Z0-9 ,;-]{13,})')
def cleanse_snippet(instr):
  # convert known XML/XHTML chars
  instr = re.sub(r'&nbsp;', ' ', instr)
  instr = re.sub(r'&quot;', '"', instr)
  instr = re.sub(r'&(uml|middot|ndash|bull|mdash|hellip);', '-', instr)
  # strip \n and \b
  instr = re.sub(r'(\\[bn])+', ' ', instr)
  # doubly-escaped HTML
  instr = re.sub(r'&amp;lt;.+?&amp;gt;', '', instr)
  instr = re.sub(r'&(amp;)+([a-z]+);', r'&\2;', instr)
  instr = re.sub(r'&amp;#\d+;', '', instr)
  # singly-escaped HTML
  # </p>, <br/>
  instr = re.sub(r'&lt;/?[a-zA-Z]+?/?&gt;', '', instr)
  # <a href=...>, <font ...>
  instr = re.sub(r'&lt;?(font|a|p|img)[^&]*/?&gt;', '', instr, re.IGNORECASE)
  # strip leftover XML escaped chars
  instr = re.sub(r'&([a-z]+|#[0-9]+);', '', instr)
  # strip repeated spaces, so maxlen works
  instr = re.sub(r'\s+', ' ', instr)

  # fix obnoxious all caps titles and snippets
  for str in re.finditer(sent_start_rx, instr):
    instr = re.sub(sent_start_rx, str.group(1)+str.group(3).lower(), instr, 1)
  
  return instr

def get_title(opp):
  """compute a clean title.  TODO: do this once and cache/memoize it"""
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
  outstr += FIELDSEP + output_field("link", BASE_PUB_URL)
  return outstr

def get_feed_fields(feedinfo):
  """Fields from the <Feed> portion of FPXML."""
  outstr = output_tag_value_renamed(feedinfo,
                                    "providerName", "feed_providerName")
  if ABRIDGED:
    return outstr
  outstr += FIELDSEP + output_tag_value(feedinfo, "feedID")
  outstr += FIELDSEP + output_tag_value_renamed(
    feedinfo, "providerID", "feed_providerID")
  outstr += FIELDSEP + output_tag_value_renamed(
    feedinfo, "providerURL", "feed_providerURL")
  outstr += FIELDSEP + output_tag_value_renamed(
    feedinfo, "description", "feed_description")
  outstr += FIELDSEP + output_tag_value_renamed(
    feedinfo, "createdDateTime", "feed_createdDateTime")
  return outstr

def output_opportunity(opp, feedinfo, known_orgs, totrecs):
  """main function for outputting a complete opportunity."""
  outstr = ""
  opp_id = xmlh.get_tag_val(opp, "volunteerOpportunityID")
  if (opp_id == ""):
    print_progress("no opportunityID")
    return totrecs, ""
  org_id = xmlh.get_tag_val(opp, "sponsoringOrganizationID")
  if (org_id not in known_orgs):
    print_progress("unknown sponsoringOrganizationID: " +\
          org_id + ".  skipping opportunity " + opp_id)
    return totrecs, ""
  org = known_orgs[org_id]
  opp_locations = opp.getElementsByTagName("location")
  opp_times = opp.getElementsByTagName("dateTimeDuration")
  repeated_fields = get_repeated_fields(feedinfo, opp, org)
  if len(opp_times) == 0:
    opp_times = [ None ]
  for opptime in opp_times:
    if opptime == None:
      startend = convert_dt_to_gbase("1971-01-01", "00:00:00-00:00", "UTC")
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
      # e.g. 2006-12-20T23:00:00/2006-12-21T08:30:00, in PST (GMT-8)
      if (start_date == ""):
        start_date = "1971-01-01"
        start_time = "00:00:00-00:00"
      startend = convert_dt_to_gbase(start_date, start_time, "UTC")
      if (end_date != "" and end_date + end_time > start_date + start_time):
        endstr = convert_dt_to_gbase(end_date, end_time, "UTC")
        startend += "/" + endstr
    duration = xmlh.get_tag_val(opptime, "duration")
    hrs_per_week = xmlh.get_tag_val(opptime, "commitmentHoursPerWeek")
    time_fields = get_time_fields(openended, duration, hrs_per_week, startend)
    if len(opp_locations) == 0:
      opp_locations = [ None ]
    for opploc in opp_locations:
      totrecs = totrecs + 1
      if PROGRESS and totrecs % 250 == 0:
        print_progress(str(totrecs)+" records generated.")
      if opploc == None:
        locstr, latlng, geocoded_loc = ("", "", "")
        loc_fields = get_loc_fields("", "0.0", "0.0", "", "")
      else:
        locstr = get_full_addr_str(opploc)
        addr, lat, lng, acc = find_geocoded_location(opploc)
        loc_fields = get_loc_fields("", str(float(lat)+1000.0),
                                    str(float(lng)+1000.0), addr,
                                    xmlh.get_tag_val(opploc, "name"))
      opp_id = compute_stable_id(opp, org, locstr, openended, duration,
                           hrs_per_week, startend)
      outstr += output_field("id", opp_id)
      outstr += repeated_fields
      outstr += time_fields
      outstr += loc_fields
      outstr += RECORDSEP
  return totrecs, outstr

def get_time_fields(openended, duration, hrs_per_week, event_date_range):
  """output time-related fields, e.g. for multiple times per event."""
  # 2010-02-26T16:00:00/2010-02-26T16:00:00
  match = re.search(r'T(\d\d):(\d\d):\d\d(\s*/\s*.+?T(\d\d):(\d\d):\d\d)?',
                    event_date_range)
  startstr = endstr = ""
  if match:
    if match.group(2):
      startstr = match.group(1) + match.group(2)
    else:
      # TODO: exception (but need a way to throw exceptions in general)
      # e.g. ignore this record, stop this feed, etc.
      pass
    if match.group(3):
      endstr = match.group(4) + match.group(5)
  time_fields = FIELDSEP + output_field("event_date_range", event_date_range)
  time_fields += FIELDSEP + output_field("startTime", startstr)
  time_fields += FIELDSEP + output_field("endTime", endstr)
  if ABRIDGED:
    return time_fields
  time_fields += FIELDSEP + output_field("openended", openended)
  time_fields += FIELDSEP + output_field("duration", duration)
  time_fields += FIELDSEP + output_field("commitmentHoursPerWeek", hrs_per_week)
  return time_fields

def get_loc_fields(location, latitude, longitude, location_string,
                   venue_name):
  """output location-related fields, e.g. for multiple locations per event."""
  # note: we don't use Google Base's "location" field because it tries to
  # geocode it (even if we pre-geocode it) then for bogus reasons, rejects
  # around 40% of our listings-- again, even if we pre-geocode them.
  loc_fields = FIELDSEP + output_field("location", location)
  loc_fields += FIELDSEP + output_field("latitude", latitude)
  loc_fields += FIELDSEP + output_field("longitude", longitude)
  loc_fields += FIELDSEP + output_field("location_string", location_string)
  if ABRIDGED:
    return loc_fields
  loc_fields += FIELDSEP + output_field("venue_name", venue_name)
  return loc_fields

def get_repeated_fields(feedinfo, opp, org):
  """output all fields that are repeated for each time and location."""
  repeated_fields = FIELDSEP + get_feed_fields(feedinfo)
  repeated_fields += FIELDSEP + get_event_reqd_fields(opp)
  repeated_fields += FIELDSEP + get_base_other_fields(opp, org)
  repeated_fields += FIELDSEP + get_direct_mapped_fields(opp, org)
  return repeated_fields

def output_header(feedinfo, opp, org):
  """fake opportunity printer, which prints the header line instead."""
  global PRINTHEAD, HEADER_ALREADY_OUTPUT
  # no matter what, only print the header once!
  if HEADER_ALREADY_OUTPUT:
    return ""
  HEADER_ALREADY_OUTPUT = True
  PRINTHEAD = True
  outstr = output_field("id", "")
  repeated_fields = get_repeated_fields(feedinfo, opp, org)
  time_fields = get_time_fields("", "", "", "")
  loc_fields = get_loc_fields("", "", "", "", "")
  PRINTHEAD = False
  return outstr + repeated_fields + time_fields + loc_fields + RECORDSEP

def convert_to_footprint_xml(instr, do_fastparse, maxrecs, progress):
  """macro for parsing an FPXML string to XML then format it."""
  #if False:
  #  # grr: RAM explosion, even with pulldom...
  #  totrecs = 0
  #  nodes = xml.dom.pulldom.parseString(instr)
  #  outstr = '<?xml version="1.0" ?>'
  #  outstr += '<FootprintFeed schemaVersion="0.1">'
  #  for eltype, node in nodes:
  #    if eltype == 'START_ELEMENT':
  #      if node.nodeName == 'VolunteerOpportunity':
  #        if progress and totrecs > 0 and totrecs % 250 == 0:
  #          print datetime.now(), ": ", totrecs, " opps processed."
  #        totrecs = totrecs + 1
  #        if maxrecs > 0 and totrecs > maxrecs:
  #          break
  #      if (node.nodeName == 'FeedInfo' or
  #          node.nodeName == 'Organization' or
  #          node.nodeName == 'VolunteerOpportunity'):
  #        nodes.expandNode(node)
  #        prettyxml = xmlh.prettyxml(node)
  #        outstr += prettyxml
  #  outstr += '</FootprintFeed>'
  #  return outstr
  if do_fastparse:
    res, numorgs, numopps = parse_footprint.parse_fast(instr, maxrecs, progress)
    return res
  else:
    # slow parse
    xmldoc = parse_footprint.parse(instr, maxrecs, progress)
    # TODO: maxrecs
    return xmlh.prettyxml(xmldoc)

def convert_to_gbase_events_type(instr, origname, fastparse, maxrecs, progress):
  """non-trivial logic for converting FPXML to google base formatting."""
  # todo: maxrecs
  outstr = ""
  print_progress("convert_to_gbase_events_type...", "", progress)

  example_org = None
  known_orgs = {}
  if fastparse:
    known_elnames = [
      'FeedInfo', 'FootprintFeed', 'Organization', 'Organizations',
      'VolunteerOpportunities', 'VolunteerOpportunity', 'abstract',
      'audienceTag', 'audienceTags', 'categoryTag', 'categoryTags',
      'city', 'commitmentHoursPerWeek', 'contactEmail', 'contactName',
      'contactPhone', 'country', 'createdDateTime', 'dateTimeDuration',
      'dateTimeDurationType', 'dateTimeDurations', 'description',
      'detailURL', 'directions', 'donateURL', 'duration', 'email',
      'endDate', 'endTime', 'expires', 'fax', 'feedID', 'guidestarID',
      'iCalRecurrence', 'language', 'latitude', 'lastUpdated', 'location',
      'locationType', 'locations', 'logoURL', 'longitude', 'minimumAge',
      'missionStatement', 'name', 'nationalEIN', 'openEnded',
      'organizationID', 'organizationURL', 'paid', 'phone', 'postalCode',
      'providerID', 'providerName', 'providerURL', 'region', 'schemaVersion',
      'sexRestrictedEnum', 'sexRestrictedTo', 'skills',
      'sponsoringOrganizationID', 'startDate', 'startTime', 'streetAddress1',
      'streetAddress2', 'streetAddress3', 'title', 'tzOlsonPath', 'virtual',
      'volunteerHubOrganizationID', 'volunteerOpportunityID',
      'volunteersFilled', 'volunteersSlots', 'volunteersNeeded', 'yesNoEnum'
      ]
    numopps = 0

    feedchunks = re.findall(
      re.compile('<FeedInfo>.+?</FeedInfo>', re.DOTALL), instr)
    for feedchunk in feedchunks:
      print_progress("found FeedInfo.", progress=progress)
      feedinfo = xmlh.simple_parser(feedchunk, known_elnames, False)

    orgchunks = re.findall(
      re.compile('<Organization>.+?</Organization>', re.DOTALL), instr)
    for orgchunk in orgchunks:
      if progress and len(known_orgs) % 250 == 0:
        print_progress(str(len(known_orgs))+" organizations seen.")
      org = xmlh.simple_parser(orgchunk, known_elnames, False)
      org_id = xmlh.get_tag_val(org, "organizationID")
      if (org_id != ""):
        known_orgs[org_id] = org
      if example_org == None:
        example_org = org

    oppchunks = re.findall(
      re.compile('<VolunteerOpportunity>.+?</VolunteerOpportunity>',
                 re.DOTALL), instr)
    for oppchunk in oppchunks:
      opp = xmlh.simple_parser(oppchunk, None, False)
      if not HEADER_ALREADY_OUTPUT:
        outstr = output_header(feedinfo, opp, example_org)
      numopps, spiece = output_opportunity(opp, feedinfo, known_orgs, numopps)
      outstr += spiece
      if (maxrecs > 0 and numopps > maxrecs):
        break

    ## note: preserves order, so diff works (vs. one sweep per element type)
    #chunks = re.findall(
    #  re.compile('<(?:Organization|VolunteerOpportunity|FeedInfo)>.+?'+
    #             '</(?:Organization|VolunteerOpportunity|FeedInfo)>',
    #             re.DOTALL), instr)
    #for chunk in chunks:
    #  node = xmlh.simple_parser(chunk, known_elnames, False)
    #  if re.search("<FeedInfo>", chunk):
    #    print_progress("found FeedInfo.", progress=progress)
    #    feedinfo = xmlh.simple_parser(chunk, known_elnames, False)
    #    continue
    #  if re.search("<Organization>", chunk):
    #    if progress and len(known_orgs) % 250 == 0:
    #      print_progress(str(len(known_orgs))+" organizations seen.")
    #    org = xmlh.simple_parser(chunk, known_elnames, False)
    #    org_id = xmlh.get_tag_val(org, "organizationID")
    #    if (org_id != ""):
    #      known_orgs[org_id] = org
    #    if example_org == None:
    #      example_org = org
    #    continue
    #  if re.search("<VolunteerOpportunity>", chunk):
    #    global HEADER_ALREADY_OUTPUT
    #    opp = xmlh.simple_parser(chunk, None, False)
    #    if numopps == 0:
    #      # reinitialize
    #      outstr = output_header(feedinfo, node, example_org)
    #    numopps, spiece = output_opportunity(opp, feedinfo, known_orgs, numopps)
    #    outstr += spiece
    #    if (maxrecs > 0 and numopps > maxrecs):
    #      break

    #numopps = 0
    #nodes = xml.dom.pulldom.parseString(instr)
    #example_org = None
    #for type,node in nodes:
    #  if type == 'START_ELEMENT':
    #    if node.nodeName == 'FeedInfo':
    #      nodes.expandNode(node)
    #      feedinfo = node
    #    elif node.nodeName == 'Organization':
    #      nodes.expandNode(node)
    #      id = xmlh.get_tag_val(node, "organizationID")
    #      if (id != ""):
    #        known_orgs[id] = node
    #      if example_org == None:
    #        example_org = node
    #    elif node.nodeName == 'VolunteerOpportunity':
    #      nodes.expandNode(node)
    #      if numopps == 0:
    #        outstr += output_header(feedinfo, node, example_org)
    #      numopps, spiece = output_opportunity(node, feedinfo, 
    #                      known_orgs, numopps)
    #      outstr += spiece
  else:
    # not fastparse
    footprint_xml = parse_footprint.parse(instr, maxrecs, progress)    
    feedinfos = footprint_xml.getElementsByTagName("FeedInfo")
    if (feedinfos.length != 1):
      print datetime.now(), "bad FeedInfo: should only be one section"
      # TODO: throw error
      sys.exit(1)
    feedinfo = feedinfos[0]
    organizations = footprint_xml.getElementsByTagName("Organization")
    for org in organizations:
      org_id = xmlh.get_tag_val(org, "organizationID")
      if (org_id != ""):
        known_orgs[org_id] = org
    opportunities = footprint_xml.getElementsByTagName("VolunteerOpportunity")
    numopps = 0
    for opp in opportunities:
      if numopps == 0:
        outstr += output_header(feedinfo, opp, organizations[0])
      numopps, spiece = output_opportunity(opp, feedinfo, known_orgs, numopps)
      outstr += spiece
  return outstr, len(known_orgs), numopps

def guess_shortname(filename):
  """from the input filename, guess which feed this is."""
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
  if re.search(r'citizencorps', filename):
    return "citizencorps"
  if re.search(r'ymca', filename):
    return "ymca"
  if re.search("habitat", filename):
    return "habitat"
  if re.search("americansolutions", filename):
    return "americansolutions"
  if re.search("spreadsheets[.]google[.]com", filename):
    return "gspreadsheet"
  if re.search("(handson|hot.footprint)", filename):
    return "handsonnetwork"
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
  if re.search(r'(seniorcorps|985148b9e3c5b9523ed96c33de482e3d)', filename):
    # note: has to come before volunteermatch
    return "seniorcorps"
  if re.search(r'(volunteermatch|cfef12bf527d2ec1acccba6c4c159687)', filename):
    return "volunteermatch"
  if re.search("christianvol", filename):
    return "christianvolunteering"
  if re.search("volunteer(two|2)", filename):
    return "volunteertwo"
  if re.search("mentorpro", filename):
    return "mentorpro"
  if re.search(r'(mpsg_feed|myproj_servegov)', filename):
    return "myproj_servegov"
  return ""

def ftp_to_base(filename, ftpinfo, instr):
  """ftp the string to base, guessing the feed name from the orig filename."""
  ftplib = __import__('ftplib')
  stringio = __import__('StringIO')

  dest_fn = guess_shortname(filename)
  if dest_fn == "":
    dest_fn = "footprint1.txt"
  else:
    dest_fn = dest_fn + "1.gz"

  if re.search(r'[.]gz$', dest_fn):
    print_progress("compressing data from "+str(len(instr))+" bytes", filename)
    gzip_fh = gzip.open(dest_fn, 'wb', 9)
    gzip_fh.write(instr)
    gzip_fh.close()
    data_fh = open(dest_fn, 'rb')
  else:
    data_fh = stringio.StringIO(instr)

  host = 'uploads.google.com'
  (user, passwd) = ftpinfo.split(":")
  print_progress("connecting to " + host + " as user " + user + "...", filename)
  ftp = ftplib.FTP(host)
  welcomestr = re.sub(r'\n', '\\n', ftp.getwelcome())
  print_progress("FTP server says: "+welcomestr, filename)
  ftp.login(user, passwd)
  print_progress("uploading filename "+dest_fn, filename)
  success = False
  while not success:
    try:
      ftp.storbinary("STOR " + dest_fn, data_fh, 8192)
      success = True
    except:
      # probably ftplib.error_perm: 553: Permission denied on server. (Overwrite)
      print_progress("upload failed-- sleeping and retrying...")
      time.sleep(1)
  if success:
    print_progress("done uploading.")
  else:
    print_progress("giving up.")
  ftp.quit()
  data_fh.close()
  
def solr_retransform(fname):
  """Create SOLR-compatible versions of a datafile"""
  print fname
  data_file = open(fname, "r")
  csv_reader = DictReader(data_file, dialect='our-dialect')
  csv_reader.next()
  fnames = csv_reader.fieldnames[:]
  fnames.append("c:eventrangeend:datetime")
  fnames.append("c:eventrangestart:datetime")
  fnamesdict = dict([(x, x) for x in fnames])
  data_file = open(fname, "r")
  # TODO: Switch to TSV - Faster and simpler
  csv_reader = DictReader(data_file, dialect='our-dialect')
  csv_writer = DictWriter(open (fname + '.transformed', 'w'),
                          dialect='excel-tab',
                          fieldnames=fnames)
  csv_writer.writerow(fnamesdict)
  for rows in csv_reader:
    for key in rows.keys():
      if key.find(':dateTime') != -1:
        rows[key] += 'Z'
      elif key.find(':integer') != -1:
        if rows[key] == '':
          rows[key] = 0
        else:
          rows[key] = int(rows[key])
      
    # Split the date range into separate fields
    # event_date_range can be either start_date or start_date/end_date
    split_date_range = rows["event_date_range"].split('/')
    rows["c:eventrangeend:datetime"] = split_date_range[0]
    if len(split_date_range) > 1:
      rows["c:eventrangestart:datetime"] = split_date_range[1]
    
    # Fix to the +1000 to lat/long hack   
    if not rows['c:latitude:float'] is None:
      rows['c:latitude:float'] = float(rows['c:latitude:float']) - 1000.0
    if not rows['c:longitude:float'] is None:
      rows['c:longitude:float'] = float(rows['c:longitude:float']) - 1000.0
      
    csv_writer.writerow(rows)
  data_file.close()
  
# TODO: add a choice of backend URL
def update_solr_index(filename, backend_url):
  """Transform a datafile and update the specified backend's index"""
  in_fname = filename + '.gz'
  out_fname = filename + '.transformed'
  # TODO: work out how to use the data string directly instead of faffing
  # around with gzip and conventional files.
  f_out = open(out_fname, 'wb')
  f_in = gzip.open(in_fname, 'rb')
  
  f_out.writelines(f_in)
  f_out.close()
  f_in.close()
  
  solr_retransform(out_fname)
   
  cmd = 'curl \'' + backend_url + \
   'update/csv?commit=true&separator=%09&escape=%10\' --data-binary ' + \
   out_fname + \
   ' -H \'Content-type:text/plain; charset=utf-8\';'
  subprocess.call(cmd, shell=True)

def guess_parse_func(inputfmt, filename):
  """from the filename and the --inputfmt,guess the input type and parse func"""

  # for development
  if inputfmt == "fpxml":
    return "fpxml", parse_footprint.parse_fast

  shortname = guess_shortname(filename)

  # FPXML providers
  fp = parse_footprint
  if shortname == "handsonnetwork":
    return "fpxml", fp.parser(
      '102', 'handsonnetwork', 'handsonnetwork', 'http://handsonnetwork.org/',
      'HandsOn Network')
  if shortname == "idealist":
    return "fpxml", fp.parser(
      '103', 'idealist', 'idealist', 'http://www.idealist.org/',
      'Idealist')
  if shortname == "volunteermatch":
    return "fpxml", fp.parser(
      '104', 'volunteermatch', 'volunteermatch',
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
    return "gspreadsheet", pgs.parse

  if shortname == "usaservice" or shortname == "usasvc":
    return "usaservice", parse_usaservice.parse

  if shortname == "craigslist" or shortname == "cl":
    return "craigslist", parse_craigslist.parse

  # legacy-- to be safe, remove after 9/1/2009
  #if shortname == "volunteermatch" or shortname == "vm":
  #  return "volunteermatch", parse_volunteermatch.parse
  #if shortname == "idealist":
  #  return "idealist", parse_idealist.parse

  print datetime.now(), "couldn't guess input format-- try --inputfmt"
  sys.exit(1)

def clean_input_string(instr):
  """run various cleanups for low-level encoding issues."""
  def cleaning_progress(msg):
    """macro"""
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
  global DEBUG, PROGRESS, FIELDSEP, RECORDSEP, ABRIDGED, OUTPUTFMT
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
  if (options.abridged):
    ABRIDGED = True
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
    outfh = urllib.urlopen(filename)
    if (re.search(r'[.]gz$', filename)):
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


def process_file(filename, options, providerName="", providerID="",
                 providerURL=""):
  shortname = guess_shortname(filename)
  inputfmt, parsefunc = guess_parse_func(options.inputfmt, filename)
  infh = open_input_filename(filename)
  print_progress("reading data...")
  # don't put this inside open_input_filename() because it could be large
  instr = infh.read()
  print_progress("done reading data.")

  # remove bad encodings etc.
  if options.clean:
    instr = clean_input_string(instr)

  # split nasty XML inputs, to help isolate problems
  if options.debug_input:
    instr = re.sub(r'><', r'>\n<', instr)

  print_progress("inputfmt: "+inputfmt)
  print_progress("outputfmt: "+options.outputfmt)
  print_status("input data: "+str(len(instr))+" bytes", shortname)

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
  if (providerURL != "" and
      footprint_xmlstr.find('<providerURL></providerURL>')):
    footprint_xmlstr = re.sub(
      '<providerURL></providerURL>',
      '<providerURL>%s</providerURL>' % providerURL, footprint_xmlstr)

  if options.test:
    # free some RAM
    del instr
    test_parse(footprint_xmlstr, options.maxrecs)
    sys.exit(0)

  fastparse = not options.debug_input
  if OUTPUTFMT == "fpxml":
    # TODO: pretty printing option
    print convert_to_footprint_xml(footprint_xmlstr, fastparse,
                                   int(options.maxrecs), PROGRESS)
    sys.exit(0)

  if OUTPUTFMT != "basetsv":
    print >> sys.stderr, datetime.now(), \
        "--outputfmt not implemented: try 'basetsv','fpbasetsv' or 'fpxml'"
    sys.exit(1)

  outstr, numorgs, numopps = convert_to_gbase_events_type(
    footprint_xmlstr, shortname, fastparse, int(options.maxrecs), PROGRESS)

  return len(footprint_xmlstr), numorgs, numopps, outstr


def main():
  """main function for cmdline execution."""
  start_time = datetime.now()
  options, args = parse_options()
  filename = args[0]
  if re.search("spreadsheets[.]google[.]com", filename):
    if OUTPUTFMT == "fpxml":
      pgs.parser_error("FPXML format not supported for "+
                       "spreadsheet-of-spreadsheets")
      sys.exit(1)
    match = re.search(r'key=([^& ]+)', filename)
    url = "http://spreadsheets.google.com/feeds/cells/" + match.group(1)
    url += "/1/public/basic"
    # to avoid hitting 80 columns
    data = {}
    updated = {}
    if PROGRESS:
      print "processing master spreadsheet", url
    maxrow, maxcol = pgs.read_gspreadsheet(url, data, updated, PROGRESS)
    header_row, header_startcol = pgs.find_header_row(data, 'provider name')

    # check to see if there's a header-description row
    header_desc = pgs.cellval(data, header_row+1, header_startcol)
    if not header_desc:
      pgs.parser_error("blank row not allowed below header row")
      sys.exit(1)
    header_desc = header_desc.lower()
    data_startrow = header_row + 1
    if header_desc.find("example") >= 0:
      data_startrow += 1

    bytes = numorgs = numopps = 0
    outstr = ""
    for row in range(data_startrow, int(maxrow)+1):
      providerName = pgs.cellval(data, row, header_startcol)
      if providerName is None or providerName == "":
        if PROGRESS:
          print "missing provider name from row "+str(row)
        break
      providerID = pgs.cellval(data, row, header_startcol+1)
      if providerID is None or providerID == "":
        if PROGRESS:
          print "missing provider ID from row "+str(row)
        break
      providerURL = pgs.cellval(data, row, header_startcol+2)
      if providerURL is None or providerURL == "":
        if PROGRESS:
          print "missing provider URL from row "+str(row)
        break
      match = re.search(r'key=([^& ]+)', providerURL)
      providerURL = "http://spreadsheets.google.com/feeds/cells/"
      providerURL += match.group(1)
      providerURL += "/1/public/basic"
      if PROGRESS:
        print "processing spreadsheet", providerURL, "name="+providerName
      providerBytes, providerNumorgs, providerNumopps, tmpstr = process_file(
        providerURL, options, providerName, providerID, providerURL)
      if PROGRESS:
        print "done processing spreadsheet: name="+providerName, \
            "records="+str(providerNumopps), \
            "url="+providerURL
      bytes += providerBytes
      numorgs += providerNumorgs
      numopps += providerNumopps
      outstr += tmpstr
  else:
    bytes, numorgs, numopps, outstr = process_file(filename, options)

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

  elapsed = datetime.now() - start_time
  # NOTE: if you change this, you also need to update datahub/load_gbase.py
  # and frontend/views.py to avoid breaking the dashboard-- other status
  # messages don't matter.
  shortname = guess_shortname(filename)
  xmlh.print_status("done parsing: output " + str(numorgs) + " organizations" +
                    " and " + str(numopps) + " opportunities" +
                    " (" + str(bytes) + " bytes): " +
                    str(int(elapsed.seconds/60)) + " minutes.",
                    shortname, PROGRESS)

if __name__ == "__main__":
  main()
