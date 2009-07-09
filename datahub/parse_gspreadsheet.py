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
parser for feed stored in a google spreadsheet
(note that this is different from other parsers inasmuch as it
expects the caller to pass in the providerID and providerName)
"""

# typical cell
#<entry>
#<id>http://spreadsheets.google.com/feeds/cells/pMY64RHUNSVfKYZKPoVXPBg
#/1/public/basic/R14C13</id>
#<updated>2009-04-28T03:29:56.957Z</updated>
#<category scheme='http://schemas.google.com/spreadsheets/2006' 
#term='http://schemas.google.com/spreadsheets/2006#cell'/>
#<title type='text'>M14</title>
#<content type='text'>ginny@arthur.edu</content>
#<link rel='self' type='application/atom+xml' href='http://spreadsheets.
#google.com/feeds/cells/pMY64RHUNSVfKYZKPoVXPBg/1/public/basic/R14C13'/>
#</entry>

import xml_helpers as xmlh
import re
import urllib
import sys
import time
from datetime import datetime

CURRENT_ROW = None

def parser_error(msg):
  if CURRENT_ROW != None:
    msg = "row "+str(CURRENT_ROW)+": "+msg
  print "parse_gspreadsheet ERROR: "+msg

def raw_recordval(record, key):
  if key in record:
    return str(record[key]).strip()
  return ""

def recordval(record, key):
  return re.sub(r'\s+', ' ', raw_recordval(record, key))

KNOWN_ORGS = {}

def get_dtval(record, field_name):
  val = recordval(record, field_name)
  if val != "" and not re.match(r'\d\d?/\d\d?/\d\d\d\d', val):
    parser_error("bad value in "+field_name+": '"+val+"'-- try MM/DD/YYYY")
  return val

def get_tmval(record, field_name):
  val = recordval(record, field_name)
  if val != "" and not re.match(r'\d?\d:\d\d(:\d\d)?', val):
    parser_error("bad value in "+field_name+": '"+val+"'-- try HH:MM:SS")
  return val

def record_to_fpxml(record):
  fpxml = ""
  fpxml += '<VolunteerOpportunity>'
  fpxml += xmlh.output_val("volunteerOpportunityID", recordval(record, 'oppid'))
  orgname = recordval(record,'SponsoringOrganization')
  if orgname not in KNOWN_ORGS:
    KNOWN_ORGS[orgname] = len(KNOWN_ORGS)
  fpxml += xmlh.output_val("sponsoringOrganizationID", KNOWN_ORGS[orgname])
  title = recordval(record,'OpportunityTitle')
  if title == "":
    parser_error("missing OpportunityTitle-- this field is required.")
  fpxml += xmlh.output_val("title", title)
  fpxml += '<dateTimeDurations>'
  fpxml += '<dateTimeDuration>'
  if ('StartDate' in record and
      recordval(record,'StartDate').find("ongoing") >= 0):
    fpxml += xmlh.output_val('openEnded', 'Yes')
  else:
    fpxml += xmlh.output_val('openEnded', 'No')
    startdtval = get_dtval(record, 'StartDate')
    if startdtval != "":
      fpxml += xmlh.output_val('startDate', startdtval)
    starttmval = get_tmval(record, 'StartTime')
    if starttmval != "":
      fpxml += xmlh.output_val('startTime', starttmval)
    enddtval = get_dtval(record, 'EndDate')
    if enddtval != "":
      fpxml += xmlh.output_val('endDate', enddtval)
    endtmval = get_tmval(record, 'EndTime')
    if endtmval != "":
      fpxml += xmlh.output_val('endTime', endtmval)
  freq = recordval(record,'Frequency').lower()
  if freq == "" or freq.find("once") >= 0:
    fpxml += '<iCalRecurrence/>'
  elif freq.find("daily") >= 0:
    fpxml += '<iCalRecurrence>FREQ=DAILY</iCalRecurrence>'
  elif freq.find("weekly") >= 0:
    fpxml += '<iCalRecurrence>FREQ=WEEKLY</iCalRecurrence>'
  elif freq.find("other") >= 0 and freq.find("week") >= 0:
    fpxml += '<iCalRecurrence>FREQ=WEEKLY;INTERVAL=2</iCalRecurrence>'
  elif freq.find("monthly") >= 0:
    fpxml += '<iCalRecurrence>FREQ=MONTHLY</iCalRecurrence>'
  else:
    parser_error("unsupported frequency: '"+recordval(record,'Frequency')+"'-- skipping")
  fpxml += xmlh.output_val('commitmentHoursPerWeek', recordval(record,'CommitmentHours'))
  fpxml += '</dateTimeDuration>'
  fpxml += '</dateTimeDurations>'
  fpxml += '<locations>'
  fpxml += '<location>'
  if recordval(record,'LocationName').find("virtual") >= 0:
    fpxml += xmlh.output_val('virtual', 'Yes')
  else:
    fpxml += xmlh.output_val('virtual', 'No')
    fpxml += xmlh.output_val('name', recordval(record,'LocationName'))
    fpxml += xmlh.output_val('streetAddress1', recordval(record,'LocationStreet'))
    fpxml += xmlh.output_val('city', recordval(record,'LocationCity'))
    fpxml += xmlh.output_val('region', recordval(record,'LocationProvince'))
    fpxml += xmlh.output_val('postalCode', recordval(record,'LocationPostalCode'))
    fpxml += xmlh.output_val('country', recordval(record,'LocationCountry'))
  fpxml += '</location>'
  fpxml += '</locations>'
  fpxml += xmlh.output_val('paid', recordval(record,'Paid'))
  fpxml += xmlh.output_val('minimumAge', recordval(record,'MinimumAge'))
  # TODO: seniors only, kidfriendly
  fpxml += xmlh.output_val('sexRestrictedTo', recordval(record,'SexRestrictedTo'))
  fpxml += xmlh.output_val('skills', recordval(record,'Skills'))
  fpxml += xmlh.output_val('contactName', recordval(record,'ContactName'))
  fpxml += xmlh.output_val('contactPhone', recordval(record,'ContactPhone'))
  fpxml += xmlh.output_val('contactEmail', recordval(record,'ContactEmail'))
  fpxml += xmlh.output_val('detailURL', recordval(record,'URL'))
  # note: preserve whitespace in description
  fpxml += xmlh.output_val('description', raw_recordval(record,'Description'))
  fpxml += '<lastUpdated olsonTZ="Etc/UTC">'
  fpxml += recordval(record,'LastUpdated') + '</lastUpdated>'
  fpxml += '</VolunteerOpportunity>'
  return fpxml

def cellval(data, row, col):
  key = 'R'+str(row)+'C'+str(col)
  if key not in data:
    return None
  return data[key]

def parse_gspreadsheet(instr, data, updated, progress):
  # look ma, watch me parse XML a zillion times faster!
  #<entry><id>http://spreadsheets.google.com/feeds/cells/pMY64RHUNSVfKYZKPoVXPBg
  #/1/public/basic/R14C15</id><updated>2009-04-28T03:34:21.900Z</updated>
  #<category scheme='http://schemas.google.com/spreadsheets/2006'
  #term='http://schemas.google.com/spreadsheets/2006#cell'/><title type='text'>
  #O14</title><content type='text'>http://www.fake.org/vol.php?id=4</content>
  #<link rel='self' type='application/atom+xml'
  #href='http://spreadsheets.google.com/feeds/cells/pMY64RHUNSVfKYZKPoVXPBg/1/
  #public/basic/R14C15'/></entry>
  regexp = re.compile('<entry>.+?(R(\d+)C(\d+))</id>'+
                      '<updated.*?>(.+?)</updated>.*?'+
                      '<content.*?>(.+?)</content>.+?</entry>', re.DOTALL)
  maxrow = maxcol = 0
  for i, match in enumerate(re.finditer(regexp, instr)):
    if progress and i > 0 and i % 250 == 0:
      print str(datetime.now())+": ", i, " cells processed."
    lastupd = re.sub(r'([.][0-9]+)?Z?$', '', match.group(4)).strip()
    #print "lastupd='"+lastupd+"'"
    updated[match.group(1)] = lastupd.strip("\r\n\t ")
    val = match.group(5).strip("\r\n\t ")
    data[match.group(1)] = val
    row = match.group(2)
    if row > maxrow:
      maxrow = row
    col = match.group(3)
    if col > maxcol:
      maxcol = col
    #print row, col, val
  return maxrow, maxcol

def read_gspreadsheet(url, data, updated, progress):
  # read the spreadsheet into a big string
  infh = urllib.urlopen(url)
  instr = infh.read()
  infh.close()
  return parse_gspreadsheet(instr, data, updated, progress)

def find_header_row(data, regexp_str):
  regexp = re.compile(regexp_str, re.IGNORECASE|re.DOTALL)
  header_row = header_startcol = -1
  for row in range(20):
    if header_row != -1:
      break
    for col in range(5):
      val = cellval(data, row, col)
      if (val and re.search(regexp, val)):
        header_row = row
        header_startcol = col
        break
  if header_row == -1:
    parser_error("no header row found: looked for "+regexp_str)
  if header_startcol == -1:
    parser_error("no header start column found")
  return header_row, header_startcol

def parse(instr, maxrecs, progress):
  # TODO: a spreadsheet should really be an object and cellval a method
  data = {}
  updated = {}
  maxrow, maxcol = parse_gspreadsheet(instr, data, updated, progress)
  # find header row: look for "opportunity title" (case insensitive)
  header_row, header_startcol = find_header_row(data, 'opportunity\s*title')

  header_colidx = {}
  header_names = {}
  header_col = header_startcol
  while True:
    header_str = cellval(data, header_row, header_col)
    if not header_str:
      break
    field_name = None
    header_str = header_str.lower()
    if header_str.find("title") >= 0:
      field_name = "OpportunityTitle"
    elif header_str.find("organization") >= 0 and header_str.find("sponsor") >= 0:
      field_name = "SponsoringOrganization"
    elif header_str.find("description") >= 0:
      field_name = "Description"
    elif header_str.find("skills") >= 0:
      field_name = "Skills"
    elif header_str.find("location") >= 0 and header_str.find("name") >= 0:
      field_name = "LocationName"
    elif header_str.find("street") >= 0:
      field_name = "LocationStreet"
    elif header_str.find("city") >= 0:
      field_name = "LocationCity"
    elif header_str.find("state") >= 0 or header_str.find("province") >= 0:
      field_name = "LocationProvince"
    elif header_str.find("zip") >= 0 or header_str.find("postal") >= 0:
      field_name = "LocationPostalCode"
    elif header_str.find("country") >= 0:
      field_name = "LocationCountry"
    elif header_str.find("start") >= 0 and header_str.find("date") >= 0:
      field_name = "StartDate"
    elif header_str.find("start") >= 0 and header_str.find("time") >= 0:
      field_name = "StartTime"
    elif header_str.find("end") >= 0 and header_str.find("date") >= 0:
      field_name = "EndDate"
    elif header_str.find("end") >= 0 and header_str.find("time") >= 0:
      field_name = "EndTime"
    elif header_str.find("contact") >= 0 and header_str.find("name") >= 0:
      field_name = "ContactName"
    elif header_str.find("email") >= 0 or header_str.find("e-mail") >= 0:
      field_name = "ContactEmail"
    elif header_str.find("phone") >= 0:
      field_name = "ContactPhone"
    elif header_str.find("website") >= 0 or header_str.find("url") >= 0:
      field_name = "URL"
    elif header_str.find("often") >= 0:
      field_name = "Frequency"
    elif header_str.find("days") >= 0 and header_str.find("week") >= 0:
      field_name = "DaysOfWeek"
    elif header_str.find("paid") >= 0:
      field_name = "Paid"
    elif header_str.find("commitment") >= 0 or header_str.find("hours") >= 0:
      field_name = "CommitmentHours"
    elif header_str.find("age") >= 0 and header_str.find("min") >= 0:
      field_name = "MinimumAge"
    elif header_str.find("kid") >= 0:
      field_name = "KidFriendly"
    elif header_str.find("senior") >= 0 and header_str.find("only") >= 0:
      field_name = "SeniorsOnly"
    elif header_str.find("sex") >= 0 or header_str.find("gender") >= 0:
      field_name = "SexRestrictedTo"
    elif header_str.find("volunteer appeal") >= 0:
      field_name = None
    else:
      parser_error("couldn't map header '"+header_str+"' to a field name.")
    if field_name != None:
      header_colidx[field_name] = header_col
      header_names[header_col] = field_name
      #print header_str, "=>", field_name
    header_col += 1

  if len(header_names) < 10:
    parser_error("too few fields found: "+str(len(header_names)))

  # check to see if there's a header-description row
  header_desc = cellval(data, header_row+1, header_startcol)
  if not header_desc:
    parser_error("blank row not allowed below header row")
  header_desc = header_desc.lower()
  data_startrow = header_row + 1
  if header_desc.find("up to") >= 0:
    data_startrow += 1

  # find the data
  global CURRENT_ROW
  CURRENT_ROW = row = data_startrow
  blankrows = 0
  MAX_BLANKROWS = 2
  volopps = '<VolunteerOpportunities>'
  numorgs = numopps = 0
  while True:
    blankrow = True
    #rowstr = "row="+str(row)+"\n"
    record = {}
    record['LastUpdated'] = '0000-00-00'
    for field_name in header_colidx:
      col = header_colidx[field_name]
      val = cellval(data, row, col)
      if val:
        blankrow = False
      else:
        val = ""
      #rowstr += "  "+field_name+"="+val+"\n"
      record[field_name] = val
      key = 'R'+str(row)+'C'+str(col)
      if (key in updated and
          updated[key] > record['LastUpdated']):
        record['LastUpdated'] = updated[key]
    if blankrow:
      blankrows += 1
      if blankrows > MAX_BLANKROWS:
        break
    else:
      numopps += 1
      blankrows = 0
      record['oppid'] = str(numopps)
      volopps += record_to_fpxml(record)
    row += 1
    CURRENT_ROW = row
  CURRENT_ROW = None
  if progress:
    print str(datetime.now())+": ", numopps, "opportunities found."
  volopps += '</VolunteerOpportunities>'

  outstr = '<?xml version="1.0" ?>'
  outstr += '<FootprintFeed schemaVersion="0.1">'
  outstr += '<FeedInfo>'
  # providerID replaced by caller
  outstr += '<providerID></providerID>'
  # providerName replaced by caller
  outstr += '<providerName></providerName>'
  outstr += '<feedID>1</feedID>'
  outstr += '<createdDateTime>%s</createdDateTime>' % xmlh.current_ts()
  # providerURL replaced by caller
  outstr += '<providerURL></providerURL>'
  outstr += '<description></description>'
  outstr += '</FeedInfo>'
  outstr += "<Organizations>"
  for orgname in KNOWN_ORGS:
    outstr += "<Organization>"
    outstr += xmlh.output_val("organizationID", KNOWN_ORGS[orgname])
    outstr += xmlh.output_val("name", orgname)
    outstr += "</Organization>"
  outstr += "</Organizations>"
  outstr += volopps
  outstr += '</FootprintFeed>'

  #outstr = re.sub(r'><', '>\n<', outstr)
  #print outstr

  return outstr, numorgs, numopps

