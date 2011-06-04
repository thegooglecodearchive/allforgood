"""
"""

import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
from google.appengine.dist import use_library
use_library('django', '1.2')

import logging
import hashlib
import time

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import db
from django.utils import simplejson  

import geocode

DEFAULT_LIST_LIMIT = 100
MAX_LIST_LIMIT = 1000

XML_WRAPPER = """<?xml version="1.0" ?>
<FootprintFeed schemaVersion="0.1">
  <FeedInfo>
    <providerID>%s</providerID>
    <providerName>%s</providerName>
    <feedID>%s</feedID>
    <createdDateTime>%s</createdDateTime>
    <providerURL>%s</providerURL>
  </FeedInfo>
  <Organizations>
    <Organization>
      <organizationID>%s</organizationID>
      <name>%s</name>
    </Organization>
  </Organizations>
  <VolunteerOpportunities>
  %s
  </VolunteerOpportunities>
</FootprintFeed>
"""

XML_ROW = """<VolunteerOpportunity>
   <volunteerOpportunityID>%s</volunteerOpportunityID>
   <title>%s</title>
   <sponsoringOrganizationID>%s</sponsoringOrganizationID>
   <dateTimeDurations>
    %s
   </dateTimeDurations>
   <locations>
    %s
  </locations>
  <contactName>%s</contactName>
  <detailURL>%s</detailURL>
  <description>%s</description>
  <lastUpdated>%s</lastUpdated>
</VolunteerOpportunity>
"""

BLANK_RSP = """
{"Response":
  {"sponsor":"",
   "tos":"0",
   "committed":"0",
   "contact_email":"%s",
   "contact_name":"",
   "contact_phone":"",
   "Results":[%s]
  }
}
"""

BLANK_ROW = """%s
{"row":"%s",
 "Opportunity_Title":"",
 "Description":"",
 "Website":"",
 "Location_Name":"",
 "Location_number___street":"",
 "Location_city":"",
 "Location_state___province":"",
 "Location_ZIP___postal_code":"",
 "Location_Country":"",
 "Start_Date":"",
 "End_Date":"",
 "How_often_does_event_happen":"",
 "Days_of_Week_Event_Repeats_On":"",
 "Special_Skills_Needed":""}
"""


class VolOpps(db.Model):
  """ key = md5 email address """
  created = db.DateTimeProperty(auto_now_add=True)
  email = db.TextProperty()
  json = db.BlobProperty()
  feed_providername = db.IntegerProperty()


class VolOpps_metadata(db.Model):
  last_feed_providername = db.IntegerProperty()
  

def get_next_feedprovidername():
  record = VolOpps_metadata.get_by_key_name('master_record')
  if not record:
    record = VolOpps_metadata(key_name = 'master_record')
    record.last_feed_providername = 6000

  rtn = record.last_feed_providername + 1
  record.last_feed_providername = rtn
  record.put()

  return rtn


def get_args(request):
  """ """
  unique_args = {}
  for arg in request.arguments():
    allvals = request.get_all(arg)
    unique_args[arg] = allvals[len(allvals)-1]
  return unique_args


def make_key(email):
  """ """
  return str(hashlib.md5(str(email).strip().lower()).hexdigest())


def put_record_json(email, json):
  """ """
  rtn = ""
  key = make_key(email)
  record = VolOpps.get_by_key_name(key)
  if not record:
    record = VolOpps(key_name = key)

  if not record.feed_providername:
    record.feed_providername = get_next_feedprovidername()

  record.email = email
  record.json = str(json)

  try:
    record.put()
    rtn = str(record.feed_providername)
  except CapabilityDisabledError:
    logging.warning(key + " set in datastore failed")
  
  return rtn


def get_record_json(email):
  """ """
  rtn = None
  key = make_key(email)
  record = VolOpps.get_by_key_name(key)
  if record:
    rtn = record.json

  return rtn


def blank_row(n = 20):  
  """ """
  rtn = ""

  def comma(row):
    if row > 1:
      return ','
    else:
      return ''

  i = 0
  while i < n:    
    i += 1
    rtn += BLANK_ROW % (comma(i), str(i))

  return rtn


class ClearRecords(webapp.RequestHandler):
  """ """
  def post(self):

    try:
      email = self.request.get("email")
      if email:
        json = get_record_json(email)
        if not json:
          json = BLANK_RSP % (email, blank_row(20))
        else:
          del_rows = self.request.get("rows").strip().split(",")
          if del_rows:
            keep_rows = []
            jo = simplejson.loads(str(json))
            if jo and jo['Response'] and jo['Response']['Results']:
              for i, jo_row in enumerate(jo['Response']['Results']):
                if jo_row['row'] not in del_rows:
                  keep_rows.append(jo_row)

              while len(keep_rows) < 20:
                keep_rows.append(simplejson.loads(BLANK_ROW % ("", "#")))

              for i, jo_row in enumerate(keep_rows):
                jo_row['row'] = str(i + 1)
                keep_rows[i] = jo_row

              jo['Response']['Results'] = keep_rows
              json = simplejson.dumps(jo)
              put_record_json(email, json)
          
          if not json:
            json = BLANK_RSP % (email, blank_row(20))

        self.response.headers['Content-Type'] = 'text/html'
        self.response.out.write(json)

    except:
      self.error(500)


class GetRecord(webapp.RequestHandler):
  """ """
  def post(self):

    try:
      email = self.request.get("email")
      if not email:
        self.redirect("/online/sample.json")
      else:
        json = get_record_json(email)
        if not json:
          json = BLANK_RSP % (email, blank_row(20))
        self.response.headers['Content-Type'] = 'text/html'
        self.response.out.write(json)

    except:
      self.error(500)


class PutRecord(webapp.RequestHandler):
  """ """
  def post(self):
    
    try:
      email = self.request.get("email")
      json = self.request.get("json")
      if email and json:
        rsp = put_record_json(email, json)
        if not rsp:
          self.error(503)
        else:
          self.response.out.write(rsp)
      else:
        self.error(400)

    except:
      self.error(500)


class ListRecords(webapp.RequestHandler):
  """ """
  def get(self):

    args = get_args(self.request)

    limit = DEFAULT_LIST_LIMIT
    if 'limit' in args:
      try:
        limit = int(args['limit'])
        if limit < 1:
          limit = 1
        if limit > MAX_LIST_LIMIT:
          limit = MAX_LIST_LIMIT
      except:
        pass

    start = 0
    if 'start' in args:
      try:
        start = int(args['start'])
        if start < 0:
          start = 0
      except:
        pass

    query = VolOpps.all(keys_only = True)
    keys = query.fetch(limit, start)
    list = []
    for key in keys:
      record = VolOpps.get(key)
      if not record.feed_providername:
        record.feed_providername = get_next_feedprovidername()
        record.put()
      list.append(str(key) + ',' + str(record.feed_providername))

    self.response.headers['Content-Type'] = 'text/html'
    self.response.out.write("\n".join(list))


class GeoCode(webapp.RequestHandler):
  """ """
  def post(self):
    args = get_args(self.request)

    if 'address' in args:
      rsp = geocode.geocode(args['address'])
      if rsp:
        self.response.out.write(rsp)
      else:
        self.error(400)


def cdata(s):
  """ """
  return "<![CDATA[%s]]>" % str(s)


def tag(tagname, value):
  """ """
  return "<%s>%s</%s>" % (tagname, str(value).strip(), tagname)


def yymmdd(jsds = None, dflt = "9999-11-31"):
  """ """
  if not jsds:
    rtn = time.strftime("%Y-%m-%d", time.gmtime())
  else:
    # expecting something like this...
    # Mon Jul 04 2011 00:00:00 GMT-0500 (CST)
    rtn = dflt
    try:
      ar = jsds.split(' ')[0:4]
      dt = time.strptime(" ".join(ar), "%a %b %d %Y")
      rtn = time.strftime("%Y-%m-%d", dt)
    except:
      pass

  rtn += "T00:00:00+0000"

  return rtn


def xml_duration(row):
  """ """
  rsp = []
  if not row['End_Date']:
    rsp.append(tag("openEnded", "Yes"))
  else:
    rsp.append(tag("openEnded", "No"))
    rsp.append(tag("endDate", yymmdd(row['End_Date'])))

  if row['Start_Date']:
    rsp.append(tag("startDate", yymmdd(row['Start_Date'], '0000-01-01')))
    
  return tag("dateTimeDuration", "\n".join(rsp))


def xml_locations(row):
  """ """
  rsp = []
  if not row['Location_Name']:
    rsp.append(tag("Virtual", "Yes"))
  else:
    rsp.append(tag("Virtual", "No"))
    rsp.append(tag("name", cdata(row['Location_Name'])))
    if row['Location_number___street']:
      rsp.append(tag("streetAddress1", cdata(row['Location_number___street'])))
    if row['Location_city']:
      rsp.append(tag("city", cdata(row['Location_city'])))
    if row['Location_state___province']:
      rsp.append(tag("region", cdata(row['Location_state___province'])))
    if row['Location_ZIP___postal_code']:
      rsp.append(tag("postalCode", cdata(row['Location_ZIP___postal_code'])))
    if row['Location_Country']:
      rsp.append(tag("country", cdata(row['Location_Country'])))

  return tag("location","\n".join(rsp))


def xml_rows(jo, orgID):
  """ """
  rtn = []
  for row in jo['Response']['Results']:
    detailURL = str(row['Website']).strip()
    title = str(row['Opportunity_Title']).strip()
    desc = str(row['Description']).strip()
    lastUpdated = yymmdd()
    if title and desc and detailURL:
       rtn.append(XML_ROW % (
             hashlib.md5(title + desc + detailURL).hexdigest(), 
             cdata(title),
             orgID, 
             xml_duration(row), 
             xml_locations(row), 
             cdata(jo['Response']['contact_name']), 
             cdata(detailURL), 
             cdata(desc), 
             lastUpdated
           )
         )

  return "\n".join(rtn)


def xml_result(jo, providerID):
  """ """
  providerName = "online spreadsheet"
  feedID = "online spreadsheet"
  createdDateTime = yymmdd()
  providerURL = "http://www.allforgood.org/online/spreadsheet.html"
  orgID = "6000"
  orgName = cdata(jo['Response']['sponsor'])

  return (providerID, providerName, feedID, createdDateTime, 
          providerURL, orgID, orgName, 
          xml_rows(jo, orgID))


class FetchRecordAsXML(webapp.RequestHandler):
  """ """
  def get(self):

    args = get_args(self.request)

    record = None
    if 'key' in args:
      record = VolOpps.get(db.Key(args['key']))
    elif 'email' in args:
      record = VolOpps.get_by_key_name(make_key(args['email']))

    if record:
      providerID = '6000'
      if 'id' in args:
        providerID = args['id']
      else:
        if record.feed_providername:
          providerID = str(record.feed_providername)
        else:
          providerID = str(get_next_feedprovidername())
  
      if record and record.json:
        if not record.feed_providername:
          try:
            record.feed_providername = int(providerID)
            record.put()
          except:
            pass
  
        jo = simplejson.loads(str(record.json))
        if jo and jo['Response'] and jo['Response']['committed'] == '1':
          xml = XML_WRAPPER % xml_result(jo, providerID)
          self.response.headers['Content-Type'] = 'text/xml'
          self.response.out.write(xml)
  

APP = webapp.WSGIApplication(
    [ ("/online/put", PutRecord),
      ("/online/get", GetRecord),
      ("/online/list", ListRecords),
      ("/online/clear", ClearRecords),
      ("/online/geo", GeoCode),
      ("/online/xml", FetchRecordAsXML)
    ], debug=True)


def main():
  """ """
  run_wsgi_app(APP)


if __name__ == '__main__':
  main()
