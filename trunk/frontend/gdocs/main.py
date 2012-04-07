"""
WORK IN PROGRESS - NOT COMPLETE

"""

import private_keys

import sys

import logging
import urllib
import urllib2

from google.appengine.api import urlfetch
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template

import gdata.docs
import gdata.docs.service

import gdata.spreadsheet
import gdata.spreadsheet.service
import gdata.alt
import gdata.alt.appengine

class SPREADSHEET_REQUEST_FORM:
  KEY = '0Av2uzfMXJ8MvdDVWSkZNMGczbGZIN3VBNmpaaDJvV2c'
  NAME = 'All for Good Spreadsheet Setup Request Form'

class SPREADSHEET_TEMPLATE:
  KEY = '0Apv-JoDtQ9x7dGgwVE1LbHkyQzF3SURJNUZneVhpTmc'
  NAME = 'All for Good Volunteer Opportunity Posting Spreadsheet Version 3.1'

COPY_URL = 'https://docs.google.com/feeds/default/private/full'
COPY_XML = """<?xml version='1.0' encoding='UTF-8'?>
<entry xmlns="http://www.w3.org/2005/Atom">
  <id>%s</id>
  <title>%s</title>
</entry>"""

ACL_URL = 'https://docs.google.com/feeds/default/private/full/%s/acl'
ACL_XML = """<?xml version='1.0' encoding='UTF-8'?>
<entry xmlns="http://www.w3.org/2005/Atom" xmlns:gAcl='http://schemas.google.com/acl/2007'>
  <category scheme='http://schemas.google.com/g/2005#kind'
    term='http://schemas.google.com/acl/2007#accessRule'/>
  <gAcl:role value='writer'/>
  <gAcl:scope type='user' value='%s'/>
</entry>"""


def login_to_SpreadsheetService(app):

  gd_client = gdata.spreadsheet.service.SpreadsheetsService()
  gdata.alt.appengine.run_on_appengine(gd_client, store_tokens=False,
                                         single_user_mode=True)

  gd_client.email = private_keys.AFG_GOOGLE_DOCS_LOGIN['username']
  gd_client.password = private_keys.AFG_GOOGLE_DOCS_LOGIN['password']
  gd_client.source = SPREADSHEET_REQUEST_FORM.NAME

  try:
    gd_client.ProgrammaticLogin()
  except:
    self.redirect("https://www.google.com/accounts/DisplayUnlockCaptcha")
    sys.exit(0)

  return gd_client


def login_to_DocsService(app):

  gd_client = gdata.docs.service.DocsService()
  gdata.alt.appengine.run_on_appengine(gd_client, store_tokens=False,
                                       single_user_mode=True)

  gd_client.email = private_keys.AFG_GOOGLE_DOCS_LOGIN['username']
  gd_client.password = private_keys.AFG_GOOGLE_DOCS_LOGIN['password']
  gd_client.source = SPREADSHEET_REQUEST_FORM.NAME

  try:
    gd_client.ProgrammaticLogin()
  except:
    app.redirect("https://www.google.com/accounts/DisplayUnlockCaptcha")
    sys.exit(0)

  return gd_client


def makePostRequest(gd_client, url, body):
  rtn = False
  rsp = ''

  request = urllib2.Request(url, data = body)
  request.add_header('GData-Version', '3.0')
  request.add_header('Authorization', 'GoogleLogin auth=' + gd_client.GetClientLoginToken())
  request.add_header('Content-Type', 'application/atom+xml')
  request.add_header('Content-Length', str(len(body)))

  try:
    rsp = urllib2.urlopen(request).read()
    rtn = True
  except urllib2.HTTPError, e:
    rsp = str(e.code) + ': ' + str(e.read())

  return rtn, rsp


def copySpreadsheet(app, from_id, to_name):

  rtn = 'ok'
  gd_client = login_to_DocsService(app)

  body = COPY_XML % (from_id, to_name)
  ok, rsp = makePostRequest(gd_client, COPY_URL, body)
  if not ok:
    rtn = rsp

  return rtn


def shareSpreadsheet(app, spreadsheet_name, submitter_email):

  rtn = 'ok'
  gd_client = login_to_DocsService(app)

  #TODO - get resource id
 
  return 'not ready yet'

  for email in ['dan@allforgood.org', 'mt1955@allforgood.org', submitter_email]:
    body = ACL_XML % email
    url = ACL_URL % resource_id
    ok, rsp = makePostRequest(gd_client, url, body)
    if not ok:
      rtn = rsp
      break
   
  return rtn


class OppsForm(webapp.RequestHandler):
  """ """
  def get(self):
    """ """

    args = {}
    for arg in self.request.arguments():
      args[arg] = self.request.get(arg)

    # get the row we are supposed to change
    row_key = args.get('row', '')
    row_key = '4/3/2012 12:23:00'

    gd_client = login_to_SpreadsheetService(self)

    query = gdata.spreadsheet.service.DocumentQuery()
    query['sq'] = 'timestamp==%s' % (row_key)
    rows = gd_client.GetListFeed(
      key = SPREADSHEET_REQUEST_FORM.KEY, wksht_id = '1',
      query = query)

    # make sure we get some results
    if not rows or len(rows.entry) < 1:
      self.error(404)
    else:
      row = rows.entry[0]
      url = row.custom['spreadsheeturl'].text
      email = row.custom['youremailaddress'].text
      if email:
        #TODO verify looks like email address
        email = email.strip()
        email = email.split(' ')[0]

      org = row.custom['nameofyourorganizationorgroup'].text
      if org:
        org = org.strip()

      if org and email and (not url or not url.startswith('http')):
        # there is no spreadsheet
        sheetname = org + ' ' + SPREADSHEET_TEMPLATE.NAME
        rsp = copySpreadsheet(self, SPREADSHEET_TEMPLATE.KEY, sheetname)
        self.response.out.write('copy: ' + rsp)

        rsp = shareSpreadsheet(self, sheetname, email)


APP = webapp.WSGIApplication(
    [ ("/oppsform.*", OppsForm)
    ], debug=True)


def main():
  """ this program starts here """
  run_wsgi_app(APP)


if __name__ == '__main__':
  main()

