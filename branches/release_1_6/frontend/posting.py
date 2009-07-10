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

from datetime import datetime
import logging
import re
import hashlib
import geocode
import utils
from xml.dom import minidom
from xml.sax.saxutils import escape
from google.appengine.ext import db

class Error(Exception):
  pass

# status codes
#  - string names to make them human-readable, i.e. easier debugging
#  - leading number provides SQL/GQL sorting without an extra field
#    (sorting is important for the moderator UI, to make sure most-
#    likely-to-be-safe is ranked higher).  Note: edited comes before
#    plain new
#  - substrings (e.g. "NEW") provide groupings, e.g. is this a 'new'
#    listing, so the moderator UI know what visual treatment to give it.

NEW_EDITED_VERIFIED = "90.NEW_EDITED_VERIFIED"
NEW_VERIFIED        = "80.NEW_VERIFIED"
NEW_EDITED          = "70.NEW_EDITED"
NEW                 = "50.NEW"
NEW_DEFERRED        = "40.NEW_DEFERRED"
ACCEPTED_MANUAL     = "10.ACCEPTED_MANUAL"
ACCEPTED_AUTOMATIC  = "10.ACCEPTED_AUTOMATIC"
REJECTED_MANUAL     = "10.REJECTED_MANUAL"
REJECTED_AUTOMATIC  = "10.REJECTED_AUTOMATIC"

class Posting(db.Model):
  """Postings going through the approval process."""
  # Key is assigned ID (not the stable ID)
  item_id = db.StringProperty(default="")
  status = db.StringProperty(default=NEW)

  # for queries, parse-out these fields - note that we don't care about datatypes
  quality_score = db.FloatProperty(default=1.0)
  creation_time = db.DateTimeProperty(auto_now_add=True)
  start_date = db.DateProperty(auto_now_add=True)

  # listing_xml is the full contents for the listing, assuming it gets approved
  # note: listing_xml also used for fulltext queries
  listing_xml = db.TextProperty(default="")

  # parse-out these fields to improve latency in the moderation UI
  title = db.StringProperty(default="")
  description = db.TextProperty(default="")
  # as per http://code.google.com/p/googleappengine/issues/detail?id=105
  # there's no point in GeoPT esp. given that we're only using this for display
  # there's even bugs (http://aralbalkan.com/1355) in GeoPT, so the heck with it.
  #todo latlong = db.StringProperty(default="")

  def statusChar(self):
    if self.status.find("ACCEPTED")>=0:
      return "A"
    if self.status.find("REJECTED")>=0:
      return "R"
    return ""
  def showInModerator(self):
    return (self.status.find("NEW")>=0)
  def isLive(self):
    return (self.status.find("ACCEPTED")>=0)
  def reset(self):
    self.status = NEW
    self.put()
  def edit(self):
    self.status = NEW_EDITED
    self.put()
  def verify(self):
    if self.status == NEW:
      self.status = NEW_VERIFIED
      self.put()
    elif self.status == NEW_EDITED:
      # TODO: how do we know the edits didn't after the email was sent?
      self.status = NEW_EDITED_VERIFIED
      self.put()
  def accept(self, type="MANUAL"):
    if type == "AUTOMATIC":
      self.status = ACCEPTED_AUTOMATIC
    else:
      self.status = ACCEPTED_MANUAL
    self.put()
  def reject(self, type="MANUAL"):
    if type == "AUTOMATIC":
      self.status = REJECTED_AUTOMATIC
    else:
      self.status = REJECTED_MANUAL
    self.put()
  def computeQualityScore(self):
    # TODO: walk the object to look for missing/bad fields
    self.quality_score = 1.0
    self.put()

def process(args):
  for arg in args:
    if arg[0] != "v":
      continue
    keystr = arg[1:]
    el = Posting.get(keystr)
    if el == None:
      # already deleted!
      continue
    # TODO: remove quality score hack-- this is how to rank in moderator UI
    if args[arg] == "A":
      el.accept()
    elif args[arg] == "R":
      el.reject()
    elif args[arg] == "V":
      el.verify()
    elif args[arg] == "X":
      logging.debug("deleting: "+keystr+"  title="+el.title)
      el.delete()
    elif args[arg] == "":
      el.reset()

def query(num=25, start=1, quality_score=0.5, start_date="2009-01-01"):
  # TODO: GQL doesn't support string-CONTAINS, limiting keyword search
  # TODO: GQL doesn't let you do inequality comparison on multiple fields.
  if quality_score == 0.0:
    sd = datetime.strptime(start_date, "%Y-%m-%d")
    q = db.GqlQuery("SELECT * FROM Posting " + 
                    "WHERE start_date >= :1 " +
                    "ORDER BY status ASC, start_date ASC " +
                    "LIMIT %d OFFSET %d" % (int(num), int(start)),
                    sd.date())
  else:
    q = db.GqlQuery("SELECT * FROM Posting " + 
                    "ORDER BY status ASC,quality_score DESC " +
                    "LIMIT %d OFFSET %d" % (int(num), int(start)))
  result_set = q.fetch(num)
  reslist = []
  for result in result_set:
    result.key = str(result.key())
    result.listing_fmtd = re.sub(r'><', '-qbr--', result.listing_xml);
    result.listing_fmtd = re.sub(r'(<?/[a-zA-Z]+-qbr--)+', '-qbr--', result.listing_fmtd);
    result.listing_fmtd = re.sub(r'>', ': ', result.listing_fmtd);
    result.listing_fmtd = re.sub(r'-qbr--', '<br/>', result.listing_fmtd)
    result.listing_fmtd = re.sub(r'(<br/>)+', '<br/>', result.listing_fmtd)
    result.status_char = result.statusChar()
    reslist.append(result)
  return reslist

def create_from_xml(xml):
  try:
    dom = minidom.parseString(xml)
  except:
    return ""

  posting = Posting(listing_xml=xml)
  posting.title = utils.xml_elem_text(dom, "title", '')
  logging.debug("create_from_xml: title="+posting.title)
  logging.debug("create_from_xml: xml="+xml)
  posting.description = utils.xml_elem_text(dom, "description", '')
  try:
    start_date = datetime.strptime(utils.xml_elem_text(
        dom, "startDate", ''), "%Y-%m-%d")
    posting.start_date = start_date.date()
  except:
    pass
    # ignore bad start date
  posting.item_id = hashlib.md5(xml+str(posting.creation_time)).hexdigest()
  posting.put()
  return posting.key()

argnames = {
  "title":1, "description":1, "skills":1, "virtual":1, "addr1":1, "addrname1":1, 
  "sponsoringOrganizationName":1, "openEnded":1, "startDate":1,
  "startTime":1, "endTime":1, "endDate":1, "contactNoneNeeded":1,
  "contactEmail":1, "contactPhone":1, "contactName":1, "detailURL":1,
  "weeklySun":1, "weeklyMon":1, "weeklyTue":1, "weeklyWed":1, "weeklyThu":1,
  "weeklyFri":1, "weeklySat":1, "biweeklySun":1, "biweeklyMon":1,
  "biweeklyTue":1, "biweeklyWed":1, "biweeklyThu":1, "biweeklyFri":1,
  "biweeklySat":1, "recurrence":1, "audienceAll":1, "audienceAge":1, 
  "minAge":1, "audienceSexRestricted":1, "sexRestrictedTo":1,
  "commitmentHoursPerWeek":1, "city":1, "region":1, "postalCode":1,
  "country":1, "street1":1, "street2":1, "location_string":1
}

# TODO: replace with a better parser-- after wasting hours, I gave up
# on strptime().  Do not add to utils.py -- this is a bad hack
def parseTimestamp(dateStr, timeStr):
  dateStr = dateStr.strip()
  grp = re.match(r'(\d?\d)[/-]?(\d?\d)[/-]?(\d\d\d\d)', dateStr)
  if grp:
    month = int(grp.group(1))
    day = int(grp.group(2))
    year = int(grp.group(3))
  else:
    grp = re.match(r'(\d?\d)[/-]?(\d?\d)[/-]?(\d\d)', dateStr)
    if grp:
      month = int(grp.group(1))
      day = int(grp.group(2))
      year = int(grp.group(3)) + 1900
    else:
      grp = re.match(r'(\d\d\d\d)[/-]?(\d\d)[/-]?(\d\d)', dateStr)
      if grp:
        year = int(grp.group(1))
        month = int(grp.group(2))
        day = int(grp.group(3))
      else:
        return None
  hour = minute = 0
  timeStr = timeStr.strip().upper()
  grp = re.match(r'(\d?\d):(\d\d) *(AM|PM)?', timeStr)
  if grp:
    hour = int(grp.group(1))
    minute = int(grp.group(2))
    ampm = grp.group(3)
    if ampm == "PM":
      hour += 12
  else:
    return None
  try:
    return datetime(year, month, day, hour, minute, 0)
  except:
    return None

def cleanup_args(vals):
  # keep only known argnames
  for key in vals:
    if key in argnames:
      vals[key] = escape(vals[key])
      #vals[key] = re.sub(r'(<!\[CDATA\[\|\]\]>)', r'', vals[key])
    else:
      vals[key] = ""
  for key in argnames:
    if key not in vals:
      vals[key] = ""

  # blank-out incompatible fields
  if vals["virtual"] != "No":
    vals["virtual"] = "Yes"
    vals["addr1"] = vals["addrname1"] = ""
  if vals["openEnded"] != "No":
    vals["openEnded"] = "Yes"
    vals["startDate"] = vals["startTime"] = ""
    vals["endDate"] = vals["endTime"] = ""

  # footprint isn't very interesting when it comes to gender
  if len(vals["sexRestrictedTo"]) < 1:
    vals["sexRestrictedTo"] = ""
  elif vals["sexRestrictedTo"][0].upper() == "M":
    vals["sexRestrictedTo"] = "M"
  elif vals["sexRestrictedTo"][0].upper() == "F":
    vals["sexRestrictedTo"] = "F"
  else:
    vals["sexRestrictedTo"] = ""

  # once, one-time or weekly, then blank-out biweekly
  if (vals["recurrence"] == "Weekly" or
      vals["recurrence"] == "No" or
      vals["recurrence"] == "Daily"):
    for arg in argnames:
      if arg.find("biweekly") == 0:
        vals[arg] == ""
  # once, one-time or biweekly, then blank-out weekly
  if (vals["recurrence"] == "BiWeekly" or
      vals["recurrence"] == "No" or
      vals["recurrence"] == "Daily"):
    for arg in argnames:
      if arg.find("weekly") == 0:
        vals[arg] == ""

def add_new_fields(vals, newvals):
  if vals["country"] == "":
    vals["country"] = "US"
  addr = vals["street1"]
  addr += " "+vals["street2"]
  addr += " "+vals["city"]
  addr += " "+vals["region"]
  addr += " "+vals["country"]
  newvals["complete_addr"] = addr
  logging.debug("post: geocoding "+addr)
  latlong = geocode.geocode(addr)
  logging.debug("post: latlong="+latlong)
  if latlong == "":
    newvals["latitude"] = newvals["longitude"] = ""
  else:
    newvals["latitude"],newvals["longitude"] = latlong.split(",")[:2]

  newvals["parsedStartDate"] = newvals["parsedStartTime"] = ""
  newvals["parsedEndDate"] = newvals["parsedEndTime"] = ""
  if vals["openEnded"] == "No":
    startTs = parseTimestamp(vals["startDate"], vals["startTime"])
    if startTs:
      newvals["parsedStartDate"] = startTs.strftime("%Y-%m-%d")
      newvals["parsedStartTime"] = startTs.strftime("%H:%M:%S")
    endTs = parseTimestamp(vals["endDate"], vals["endTime"])
    if endTs:
      newvals["parsedEndDate"] = endTs.strftime("%Y-%m-%d")
      newvals["parsedEndTime"] = endTs.strftime("%H:%M:%S")
  newvals["computedMinAge"] = 0
  if vals["audienceAge"] == "seniors":
    newvals["computedMinAge"] = 60
  elif vals["audienceAge"] == "teens":
    newvals["computedMinAge"] = 13
  elif vals["audienceAge"] == "anyage":
    newvals["computedMinAge"] = 0
  else:
    try:
      newvals["computedMinAge"] = int(vals["minAge"])
    except:
      newvals["computedMinAge"] = 0
  try:
    newvals["computedCommitmentHoursPerWeek"] = int(vals["commitmentHoursPerWeek"])
    if newvals["computedCommitmentHoursPerWeek"] < 0:
      newvals["computedCommitmentHoursPerWeek"] = 0
  except:
    newvals["computedCommitmentHoursPerWeek"] = 0


def create_from_args(vals, computed_vals):
  # note: don't need to worry (much) about hacked-forms because we're
  # using CAPTCHA to avoid bot submissions.
  cleanup_args(vals)
  add_new_fields(vals, computed_vals)
  if vals["virtual"] == 'No' and computed_vals["latitude"] == "":
    return 402, "", "cannot find address: '"+computed_vals["complete_addr"]+"'"

  xml = "<VolunteerOpportunity>"
  if vals["recaptcha_response_field"] == "test":
    # basic security measure
    xml += "<isTest>Yes</isTest>"
    vals["title"] = "T:" + vals["title"]
    vals["description"] = "TEST DELETEME: " + vals["description"]
  # TODO: organization
  #xml += "<volunteerOpportunityID>%d</volunteerOpportunityID>" % (item_id)
  #xml += "<sponsoringOrganizationIDs><sponsoringOrganizationID>%d</sponsoringOrganizationID></sponsoringOrganizationIDs>" % (item_id)
  #xml += "<volunteerHubOrganizationIDs><volunteerHubOrganizationID>%s</volunteerHubOrganizationID></volunteerHubOrganizationIDs>" % ("")
  xml += "<title>%s</title>" % (vals["title"])
  xml += "<description>%s</description>" % (vals["description"])
  xml += "<skills>%s</skills>" % (vals["skills"])
  xml += "<minimumAge>%s</minimumAge>" % (str(computed_vals["computedMinAge"]))
  xml += "<detailURL>%s</detailURL>" % (vals["detailURL"])
  xml += "<locations>"
  xml += "<location>"
  xml += "<name>%s</name>" % (vals["addrname1"])
  xml += "<city>%s</city>" % (vals["city"])
  xml += "<region>%s</region>" % (vals["region"])
  xml += "<postalCode>%s</postalCode>" % (vals["postalCode"])
  xml += "<country>%s</country>" % (vals["country"])
  xml += "<latitude>%s</latitude>" % (computed_vals["latitude"])
  xml += "<longitude>%s</longitude>" % (computed_vals["longitude"])
  xml += "</location>"
  xml += "</locations>"
  # TODO: category tags
  #xml += "<categoryTags>"
  #xml += "<categoryTag>Community</categoryTag>"
  #xml += "</categoryTags>"
  xml += "<dateTimeDurations>"
  xml += "<dateTimeDuration>"
  xml += "<openEnded>%s</openEnded>" % (vals["openEnded"])
  if vals["openEnded"] == "No":
    xml += "<startDate>%s</startDate>" % (computed_vals["startDate"])
    xml += "<startTime>%s</startTime>" % (computed_vals["startTime"])
    xml += "<endDate>%s</endDate>" % (computed_vals["endDate"])
    xml += "<endTime>%s</endTime>" % (computed_vals["endTime"])
  xml += "<commitmentHoursPerWeek>%d</commitmentHoursPerWeek>" % \
      (computed_vals["computedCommitmentHoursPerWeek"])
  xml += "</dateTimeDuration>"
  xml += "</dateTimeDurations>"
  xml += "</VolunteerOpportunity>"
  #logging.info(re.sub(r'><', '>\n<', xml))
  item_id = create_from_xml(xml)
  return 200, item_id, xml

def createTestDatabase():
  id1 = create_from_xml("<VolunteerOpportunity><volunteerOpportunityID>1001</volunteerOpportunityID><sponsoringOrganizationIDs><sponsoringOrganizationID>1</sponsoringOrganizationID></sponsoringOrganizationIDs><volunteerHubOrganizationIDs><volunteerHubOrganizationID>3011</volunteerHubOrganizationID></volunteerHubOrganizationIDs><title>Be a Business Mentor - Trenton, NJ &amp; Beyond</title><dateTimeDurations><dateTimeDuration><openEnded>Yes</openEnded><duration>P6M</duration><commitmentHoursPerWeek>4</commitmentHoursPerWeek></dateTimeDuration></dateTimeDurations><locations><location><city>Trenton</city><region>NJ</region><postalCode>08608</postalCode></location><location><city>Berkeley</city><region>CA</region><postalCode>94703</postalCode></location><location><city>Santa Cruz</city><region>CA</region><postalCode>95062</postalCode></location></locations><categoryTags><categoryTag>Community</categoryTag><categoryTag>Computers &amp; Technology</categoryTag><categoryTag>Employment</categoryTag></categoryTags><minimumAge>21</minimumAge><skills>In order to maintain the integrity of the MicroMentor program, we require that our Mentor volunteers have significant business experience and expertise, such as: 3 years of business ownership experience</skills><detailURL>http://www.volunteermatch.org/search/index.jsp?l=08540</detailURL><description>This is where you come in. Simply by sharing your business know-how, you can make a huge difference in the lives of entrepreneurs from low-income and marginalized communities, helping them navigate the opportunities and challenges of running a business and improving their economic well-being and creating new jobs where they are most needed.</description></VolunteerOpportunity>")
  id2 = create_from_xml("<VolunteerOpportunity><volunteerOpportunityID>2001</volunteerOpportunityID><sponsoringOrganizationIDs><sponsoringOrganizationID>2</sponsoringOrganizationID></sponsoringOrganizationIDs><title>DODGEBALL TO HELP AREA HUNGRY</title><dateTimeDurations><dateTimeDuration><openEnded>No</openEnded><startDate>2009-02-22</startDate><endDate>2009-02-22</endDate><startTime>18:45:00</startTime><endTime>21:00:00</endTime></dateTimeDuration><dateTimeDuration><openEnded>No</openEnded><startDate>2009-02-27</startDate><endDate>2009-02-27</endDate><startTime>18:45:00</startTime><endTime>21:00:00</endTime></dateTimeDuration></dateTimeDurations><locations><location><city>West Windsor</city><region>NJ</region><postalCode>08550</postalCode></location></locations><audienceTags><audienceTag>Teens</audienceTag><audienceTag>High School Students</audienceTag></audienceTags><categoryTags><categoryTag>Community</categoryTag><categoryTag>Homeless &amp; Hungry</categoryTag><categoryTag>Hunger</categoryTag></categoryTags><minimumAge>14</minimumAge><skills>Must be in High School</skills><detailURL>http://www.volunteermatch.org/search/opp451561.jsp</detailURL><description>The Mercer County Quixote Quest Teen Volunteer Club is hosting a FUN Dodgeball Tournament at Mercer County College on Sunday afternoon, February 22nd. The proceeds from the event will bebefit the Trenton Area Soup Kitchen. Teens are invited to enter a team of six...with at least three female players (3 guys and 3 girls or more girls). Each team playing will bring a $50 entry fee and a matching sponsor donation of $50. (Total of $100 from each team).</description><lastUpdated olsonTZ=\"America/Denver\">2009-02-02T19:02:01</lastUpdated></VolunteerOpportunity>")
  id3 = create_from_xml("<VolunteerOpportunity><volunteerOpportunityID>2002</volunteerOpportunityID><sponsoringOrganizationIDs><sponsoringOrganizationID>2</sponsoringOrganizationID></sponsoringOrganizationIDs><title>YOUNG ADULT TO HELP GUIDE MERCER COUNTY TEEN VOLUNTEER CLUB</title><volunteersNeeded>3</volunteersNeeded><dateTimeDurations><dateTimeDuration><openEnded>No</openEnded><startDate>2009-01-01</startDate><endDate>2009-05-31</endDate><iCalRecurrence>FREQ=WEEKLY;INTERVAL=2</iCalRecurrence><commitmentHoursPerWeek>2</commitmentHoursPerWeek></dateTimeDuration></dateTimeDurations><locations><location><city>Mercer County</city><region>NJ</region><postalCode>08610</postalCode></location></locations><audienceTags><audienceTag>Teens</audienceTag></audienceTags><categoryTags><categoryTag>Community</categoryTag><categoryTag>Children &amp; Youth</categoryTag></categoryTags><skills>Be interested in promoting youth volunteerism. Be available two Tuesday evenings per month.</skills><detailURL>http://www.volunteermatch.org/search/opp200517.jsp</detailURL><description>Quixote Quest is a volunteer club for teens who have a passion for community service. The teens each volunteer for their own specific cause. Twice monthly, the club meets. At the club meetings the teens from different high schools come together for two hours to talk about their volunteer experiences and spend some hang-out time together that helps them bond as fraternity...family. Quixote Quest is seeking young adults roughly between 20 and 30 years of age who would be interested in being a guide and advisor to the teens during these two evening meetings a month.</description><lastUpdated olsonTZ=\"America/Denver\">2008-12-02T19:02:01</lastUpdated></VolunteerOpportunity>")
  return (id1,id2,id3)


    

