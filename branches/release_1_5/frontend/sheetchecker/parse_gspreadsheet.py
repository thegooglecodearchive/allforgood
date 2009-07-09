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

# TODO: share this code between frontend and datahub
# see http://code.google.com/p/footprint2009dev/issues/detail?id=150


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

import re
import logging
from google.appengine.api import urlfetch
import geocode

MAX_BLANKROWS = 2

# TODO: right thing is to create a class for spreadsheets...
CURRENT_ROW = None
MESSAGES = []
DATA = None
HEADER_STARTCOL = None
HEADER_ROW = None

def parser_error(msg):
  """capture an error in its current context."""
  global MESSAGES
  if CURRENT_ROW != None:
    msg = "row "+str(CURRENT_ROW)+": "+msg
    msg += "<br/>\n&nbsp;&nbsp;&nbsp;starting with: "
    for col in range(5):
      val = cellval(CURRENT_ROW, col)
      if val == None:
        val = ""
      msg += val+" | "
  MESSAGES.append("ERROR: "+msg)

def raw_recordval(record, key):
  """get a cell value, or empty string."""
  if key in record:
    return str(record[key]).strip()
  return ""

def recordval(record, key):
  """get a cell value, replacing whitespace with space."""
  return re.sub(r'\s+', ' ', raw_recordval(record, key))

KNOWN_ORGS = {}

def get_dtval(record, field_name):
  """parse a field as a datetime."""
  val = recordval(record, field_name)
  if (val != "" and not re.match(r'\d\d?/\d\d?/\d\d\d\d', val)):
    parser_error("bad value in "+field_name+": '"+val+"'-- try MM/DD/YYYY")
  return val

def get_tmval(record, field_name):
  """parse a field as a time-of-day."""
  val = recordval(record, field_name)
  if (val != "" and not re.match(r'\d?\d:\d\d(:\d\d)?', val)):
    parser_error("bad value in "+field_name+": '"+val+"'-- try HH:MM:SS")
  return val

def get_boolval(record, field_name):
  """parse a field as a yes/no field-- note that blank is allowed."""
  val = recordval(record, field_name)
  if val.lower() not in ["y", "yes", "n", "no", ""]:
    # TODO: support these alternates in the datahub!
    parser_error("bad value in "+field_name+": '"+val+"'-- try 'Yes' or 'No'")
  return val

def get_intval(record, field_name):
  """parse a field as a time-of-day."""
  val = recordval(record, field_name)
  if val != "" and not re.match('[0-9]+', val):
    parser_error("bad value in "+field_name+": '"+val+"'-- try a number")
  return val

def get_minlen(record, field_name, minlen):
  """parse a field as a minlen string."""
  val = recordval(record, field_name)
  if val == "":
    parser_error("missing value in "+field_name+": '"+val+"'-- field required.")
  elif len(val) < minlen:
    parser_error("value not long enough in "+field_name+": '"+val+"'-- "+
                 "requires %d characters" % minlen)
  return val

def get_blank(record, field_name, reason=" in this case."):
  """parse a field as a string that must be blank."""
  val = recordval(record, field_name)
  if val == "":
    return ""
  else:
    parser_error("field "+field_name+" must be blank"+reason)
  return val

def cellval(row, col):
  """get a single cell value."""
  key = 'R'+str(row)+'C'+str(col)
  if key not in DATA:
    return None
  return DATA[key]

def parse_gspreadsheet(instr, updated):
  """load a spreadsheet into a two dimensional array."""
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
  for match in re.finditer(regexp, instr):
    lastupd = re.sub(r'([.][0-9]+)?Z?$', '', match.group(4)).strip()
    #print "lastupd='"+lastupd+"'"
    updated[match.group(1)] = lastupd.strip("\r\n\t ")
    val = match.group(5).strip("\r\n\t ")
    DATA[match.group(1)] = val
    row = match.group(2)
    if row > maxrow:
      maxrow = row
    col = match.group(3)
    if col > maxcol:
      maxcol = col
    #print row, col, val
  return maxrow, maxcol

def find_header_row(regexp_str):
  """location the header row in a footprint spreadsheet."""
  regexp = re.compile(regexp_str, re.IGNORECASE|re.DOTALL)
  global HEADER_ROW, HEADER_STARTCOL
  HEADER_ROW = HEADER_STARTCOL = None
  for row in range(20):
    if HEADER_ROW:
      break
    for col in range(5):
      val = cellval(row, col)
      if (val and re.search(regexp, val)):
        HEADER_ROW = row
        HEADER_STARTCOL = col
        break
  if HEADER_ROW == None or HEADER_STARTCOL == None:
    parser_error("failed to parse this as a footprint spreadsheet. "+
                 "No header row found: looked for "+regexp_str)

def parse(instr):
  """main function for parsing footprint spreadsheets."""
  # TODO: a spreadsheet should really be an object and cellval a method
  global DATA, MESSAGES, CURRENT_ROW
  DATA = {}
  MESSAGES = []
  CURRENT_ROW = None

  updated = {}
  parse_gspreadsheet(instr, updated)
  # find header row: look for "opportunity title" (case insensitive)
  find_header_row('opportunity\s*title')
  if not HEADER_ROW or not HEADER_STARTCOL:
    return DATA, MESSAGES

  header_colidx = {}
  header_names = {}
  header_col = HEADER_STARTCOL
  while True:
    header_str = cellval(HEADER_ROW, header_col)
    if not header_str:
      break
    field_name = None
    header_str = header_str.lower()
    if header_str.find("title") >= 0:
      field_name = "OpportunityTitle"
    elif header_str.find("organization") >= 0 and \
          header_str.find("sponsor") >= 0:
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
  header_desc = cellval(HEADER_ROW+1, HEADER_STARTCOL)
  if not header_desc:
    parser_error("blank row not allowed below header row")
  header_desc = header_desc.lower()
  data_startrow = HEADER_ROW + 1
  if header_desc.find("up to") >= 0:
    data_startrow += 1

  # find the data
  CURRENT_ROW = data_startrow
  blankrows = 0
  numopps = 0
  while True:
    blankrow = True
    #rowstr = "row="+str(row)+"\n"
    record = {}
    record['LastUpdated'] = '0000-00-00'
    for field_name in header_colidx:
      col = header_colidx[field_name]
      val = cellval(CURRENT_ROW, col)
      if val:
        blankrow = False
      else:
        val = ""
      #rowstr += "  "+field_name+"="+val+"\n"
      record[field_name] = val
      key = 'R'+str(CURRENT_ROW)+'C'+str(col)
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
      get_minlen(record, 'OpportunityTitle', 4)
      get_minlen(record, 'Description', 15)
      location_name = get_minlen(record, 'LocationName', 4)
      if location_name == "virtual":
        is_virtual = True
      elif location_name.lower() == "virtaul" or location_name.lower() == "virtual":
        parser_error("misspelled location name: "+location_name+
                     " -- perhaps you meant 'virtual'?  (note spelling)")
        is_virtual = True
      else:
        is_virtual = False

      if is_virtual:
        reason = " for virtual opportunities-- if you want both a location and"
        reason += " a virtual opportunity, then provide two separate records."
        get_blank(record, "LocationStreet", reason)
        get_blank(record, "LocationCity", reason)
        get_blank(record, "LocationProvince", reason)
        get_blank(record, "LocationPostalCode", reason)
        get_blank(record, "LocationCountry", reason)
      else:
        # TODO: appengine 30sec timeouts render this ambiguous/confuse for users
        check_locations = False
        if check_locations:
          addr = recordval(record, "LocationStreet")
          addr += " "+recordval(record, "LocationCity")
          addr += " "+recordval(record, "LocationProvince")
          addr += " "+recordval(record, "LocationPostalCode")
          addr += " "+recordval(record, "LocationCountry")
          latlong = geocode.geocode(addr)
          if latlong == "":
            parser_error("could not convert '"+addr+"' to a location "+
                         "on the map: changing the address will help your "+
                         "listing be found by users.")

      start_date = recordval(record, "StartDate")
      if start_date == "ongoing":
        ongoing = True
      elif start_date.lower().find("ong") == 0:
        parser_error("misspelled Start Date: "+start_date+
                     " -- perhaps you meant 'ongoing'?  (note spelling)")
        ongoing = True
      elif start_date == "":
        parser_error("Start Date may not be blank.")
        ongoing = True
      else:
        ongoing = False
      if ongoing:
        start_time = recordval(record, "StartTime")
        if start_time != "" and start_time != "ongoing":
          parser_error("ongoing event should have blank Start Time.")
        end_date = recordval(record, "EndDate")
        if end_date != "" and end_date != "ongoing":
          parser_error("ongoing event should have blank End Date.")
        end_time = recordval(record, "EndTime")
        if end_time != "" and end_time != "ongoing":
          parser_error("ongoing event should have blank End Time.")
      else:
        get_dtval(record, "StartDate")
        get_tmval(record, "StartTime")
        get_dtval(record, "EndDate")
        get_tmval(record, "EndTime")
      email = recordval(record, "ContactEmail")
      if email != "" and email.find("@") == -1:
        parser_error("malformed email address: "+email)
      url = recordval(record, "URL")

      # TODO: appengine 30sec timeouts render this ambiguous/confuse for users
      check_urls = False
      if check_urls:
        try:
          fetch_result = urlfetch.fetch(url)
          if fetch_result.status_code >= 400:
            parser_error("problem fetching url '"+url+"': HTTP status code "+
                         fetch_result.status_code)
        except urlfetch.InvalidURLError:
          parser_error("invalid url '"+url+"'")
        except urlfetch.ResponseTooLargeError:
          parser_error("problem fetching url '"+url+"': response too large")
        except:
          parser_error("problem fetching url '"+url+"'")
        
      daysofweek = recordval(record, "DaysOfWeek").split(",")
      for dow in daysofweek:
        lcdow = dow.strip().lower()
        if lcdow not in ["sat", "saturday",
                         "sun", "sunday",
                         "mon", "monday",
                         "tue", "tues", "tuesday",
                         "wed", "weds", "wednesday",
                         "thu", "thur", "thurs", "thursday",
                         "fri", "friday", ""]:
          # TODO: support these alternates in the datahub!
          parser_error("malformed day of week: '%s'" % dow)
      get_boolval(record, "Paid")
      get_intval(record, "CommitmentHours")
      get_intval(record, "MinimumAge")
      get_boolval(record, "KidFriendly")
      get_boolval(record, "SeniorsOnly")
      sexrestrict = recordval(record, "SexRestrictedTo")
      if sexrestrict.lower() not in ["women", "men", "either", ""]:
        parser_error("bad SexRestrictedTo-- try Men, Women, Either or (blank).")
      org = recordval(record, 'SponsoringOrganization')
      if org == "":
        parser_error("missing Sponsoring Organization-- this field is required."+
                     "  (it can be an informal name, or even a person's name).")
      else:
        get_minlen(record, 'SponsoringOrganization', 4)
      freq = recordval(record, 'Frequency').lower()
      if not (freq == "" or freq == "once" or freq == "daily" or
              freq == "weekly" or freq == "every other week" or 
              freq == "monthly"):
        parser_error("unsupported frequency: '"+
                     recordval(record, 'Frequency')+"'")
    CURRENT_ROW += 1
  if len(MESSAGES) == 0:
    MESSAGES.append("spreadsheet parsed correctly!  Feel free to submit.")
  return DATA, MESSAGES

