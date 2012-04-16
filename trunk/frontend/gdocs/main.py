"""
WORK IN PROGRESS - NOT COMPLETE

"""

import private_keys

import sys

import logging
import urllib
import urllib2
from datetime import datetime

from google.appengine.api import urlfetch
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.runtime import DeadlineExceededError

import BeautifulSoup

import gdata.docs
import gdata.docs.service

import gdata.spreadsheet
import gdata.spreadsheet.service
import gdata.alt
import gdata.alt.appengine

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
%s
</entry>"""

ACL_READER_XML="""
<gAcl:withKey key='[ACL KEY]'><gAcl:role value='reader' /></gAcl:withKey>
<gAcl:scope type='default' />
"""

ACL_WRITER_XML = """
<gAcl:role value='writer'/>
<gAcl:scope type='user' value='%s'/>
"""

def getXMLValue(app, xml_str, tag):

  rtn = ''
  try:
    soup = BeautifulSoup.BeautifulStoneSoup(xml_str)
  except:
    app.response.out.write('err: could not parse ' + xml_str)
    return rtn

  node = soup.find(tag)
  if not node:
    app.response.out.write('err: could not find ' + tag + '\n')
  else:
    rtn = soup.find(tag).string

  return rtn
   

def login_to_SpreadsheetService(app):

  gd_client = gdata.spreadsheet.service.SpreadsheetsService()
  gdata.alt.appengine.run_on_appengine(gd_client, store_tokens=False,
                                         single_user_mode=True)

  gd_client.email = private_keys.AFG_GOOGLE_DOCS_LOGIN['username']
  gd_client.password = private_keys.AFG_GOOGLE_DOCS_LOGIN['password']
  gd_client.source = private_keys.SPREADSHEET_REQUEST_FORM.NAME

  try:
    gd_client.ProgrammaticLogin()
  except:
    app.redirect("https://www.google.com/accounts/DisplayUnlockCaptcha")
    sys.exit(0)

  return gd_client


def login_to_DocsService(app):

  gd_client = gdata.docs.service.DocsService()
  gdata.alt.appengine.run_on_appengine(gd_client, store_tokens=False,
                                       single_user_mode=True)

  gd_client.email = private_keys.AFG_GOOGLE_DOCS_LOGIN['username']
  gd_client.password = private_keys.AFG_GOOGLE_DOCS_LOGIN['password']
  gd_client.source = private_keys.SPREADSHEET_REQUEST_FORM.NAME

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
    if e.code == 201:
      rtn = True
      rsp = e.read()
    elif e.code == 400:
      rsp = e.read()
      if rsp.find('successfully shared') >= 0:
        rtn = True
    elif e.code == 409:
      rtn = True
      rsp = e.read()
    else:
      rsp = str(e.code) + ': ' + str(e.read())

  return rtn, rsp


def copySpreadsheet(app, from_id, to_name):

  gd_client = login_to_DocsService(app)
  body = COPY_XML % (from_id, to_name)
  return makePostRequest(gd_client, COPY_URL, body)


def shareSpreadsheet(app, id, submitter_email_list):

  rtn = True 
  rsp = 'unknown error'
  gd_client = login_to_DocsService(app)

  resource_id = 'spreadsheet:' + id

  body = ACL_XML % ACL_READER_XML
  url = ACL_URL % resource_id
  ok, rsp = makePostRequest(gd_client, url, body)
  if not ok:
    rtn = False
  else:
    email_list = private_keys.GDOCS_ADMIN_LIST
    email_list.extend(submitter_email_list)
    for email in email_list:
      body = ACL_XML % (ACL_WRITER_XML % email)
      url = ACL_URL % resource_id
      ok, rsp = makePostRequest(gd_client, url, body)
      if not ok:
        rtn = False
        break
   
  return rtn, rsp


class OppsForm(webapp.RequestHandler):
  """ """
  def get(self):
    """ """

    args = {}
    for arg in self.request.arguments():
      args[arg] = self.request.get(arg)

    # get the row we are supposed to change
    # eg, row_key = '4/3/2012 12:23:00'

    row_key = args.get('row', '')
    if not row_key:
      self.response.out.write('err: no key')
      return

    gd_client = login_to_SpreadsheetService(self)

    query = gdata.spreadsheet.service.DocumentQuery()
    query['sq'] = 'timestamp==%s' % (row_key)
    rows = gd_client.GetListFeed(key = private_keys.SPREADSHEET_REQUEST_FORM.KEY, wksht_id = '1', query = query)

    # make sure we get some results
    if not rows or len(rows.entry) < 1:
      self.response.out.write('err: could not find ' + row_key + ' in form' + '\n')
    else:
      row = rows.entry[0]
      url = row.custom['spreadsheeturl'].text

      email_list = []
      email_cell = row.custom['youremailaddress'].text
      if email_cell:
        email_cell = email_cell.replace(',', ' ')
        while email_cell.find('  ') >= 0:
          email_cell = email_cell.replace('  ', ' ')
        email_cell = email_cell.strip()
        raw_list = email_cell.split(' ')
        for email in raw_list:
          #TODO: verify this really looks like an email address
          if len(email) > 5 and email.find('@') > 0 and email.find('.') > 0:
            email_list.append(email)

      org = row.custom['nameofyourorganizationorgroup'].text
      if org:
        org = org.strip()

      if not org:
        self.response.out.write('err: no org' + '\n')
        return

      if len(email_list) < 1:
        self.response.out.write('err: no email' + '\n')
        return

      if url and url.startswith('http'):
        self.response.out.write('ok: has spreadsheet' + '\n')
        return

      # there is no spreadsheet
      sheetname = org + ' ' + private_keys.SPREADSHEET_TEMPLATE.NAME
      ok, rsp = copySpreadsheet(self, private_keys.SPREADSHEET_TEMPLATE.KEY, sheetname)
      if not ok:
        self.response.out.write('err: could not copy spreadsheet\n' + rsp + '\n')
        return
      else:
        # <id>spreadsheet%3A...</gd:resourceId>
        id = getXMLValue(self, rsp, 'id').replace('https://docs.google.com/feeds/id/spreadsheet%3A', '')
        ok, rsp = shareSpreadsheet(self, id, email_list)
        if not ok:
          self.response.out.write('err: could not share ' + id + '\n' + str(rsp) + '\n')
          return
        else:
          updated_row = {}
          for k, v in row.custom.iteritems():
            updated_row[k] = v.text if v.text else ''

          spreadsheet_url = 'https://docs.google.com/a/allforgood.org/spreadsheet/ccc?key=' + id
          updated_row['spreadsheeturl'] = spreadsheet_url
          updated_row['notified'] = str(datetime.now())

          try:
            gd_client.UpdateRow(row, updated_row)
          except:
            self.response.out.write('err: could not update row in ' + id + '\n')
            return

          query = gdata.spreadsheet.service.DocumentQuery()
          query['sq'] = 'linktocheckspreadsheet==SHEETCHECKER_LINK'
          rows = gd_client.GetListFeed(key = id, wksht_id = '1', query = query)
          if not rows or len(rows.entry) < 1:
            self.response.out.write('err: could not get check link in ' + id + '\n')
          else:
            row = rows.entry[0]
            if row:
              updated_row = {}
              for k, v in row.custom.iteritems():
                updated_row[k] = v.text if v.text else ''

              url = 'http://www.allforgood.org/sheetchecker/check?url=' + urllib.quote(spreadsheet_url)
              updated_row['linktocheckspreadsheet'] = url
              try:
                gd_client.UpdateRow(row, updated_row)
              except:
                self.response.out.write('err: could not update check link in ' + id)
                return

              self.response.out.write('ok' + '\n')


class OppsFeed(webapp.RequestHandler):
  """ """
  def get(self):
    """ """

    args = {}
    for arg in self.request.arguments():
      args[arg] = self.request.get(arg)
    id = args.get('id', '')
    if id:
      gd_client = login_to_SpreadsheetService(self)
      rsp = gd_client.GetCellsFeed(key = id)
      self.response.headers['Content-Type'] =  'application/atom+xml; charset=UTF-8'
      self.response.out.write(str(rsp))


APP = webapp.WSGIApplication(
    [("/oppsfeed.*", OppsFeed),
     ("/oppsform.*", OppsForm),
    ], debug=True)


def main():
  """ this program starts here """
  try:
    run_wsgi_app(APP)
  except DeadlineExceededError:
    print 'retry\n'


if __name__ == '__main__':
  main()

