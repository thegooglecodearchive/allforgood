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
export main().
"""

import re
import logging
import hashlib
from datetime import datetime
from string import strip

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

import utils 
import models
from fastpageviews import pagecount
from testapi import helpers

QT = "%s%s%s" % ("ec813d6d0c96f3a562c70d78b7ac98d7ec2cfcaaf44cbd7",
                 "ac897ca3481e27a777398da97d0b93bbe0f5633f6203ff3",
                 "b77ea55f62cf002ad7e4b5ec3f89d18954")

# http://code.google.com/appengine/docs/python/datastore/typesandpropertyclasses.html
MAX_FIELD_TYPES = 8
FIELD_TYPE_BOOL = 0
FIELD_TYPE_INT = 1
FIELD_TYPE_LONG = 2
FIELD_TYPE_FLOAT = 3
FIELD_TYPE_STR = 4
FIELD_TYPE_DATETIME = 5
FIELD_TYPE_DATE = 6
FIELD_TYPE_REF = 7

# The maximum number of rows GQL
# at this time will return
GQL_MAX_ROWS = 1000

ROW_MARKER_LEN = 4
ROW_MARKER = "row="

USAGE = """
<pre>
/export/TABLENAME.tsv, eg. UserStats.tsv
/export/TABLENAME/TABLENAME_BACKUP, eg. UserInfo/UserInfo_20090416
</pre>
"""

class Fail(Exception):
  """
  handle errors
  """
  def __init__(self, message):
    pagecount.IncrPageCount("export.Fail", 1)
    if hasattr(Exception, '__init__'):
      Exception.__init__(self)
    logging.error("see /export/ for usage")
    logging.error(message)

class ShowUsage(webapp.RequestHandler):
  """ show user how to export a table """
  def __init__(self):
    if hasattr(webapp.RequestHandler, '__init__'):
      webapp.RequestHandler.__init__(self)

  def response(self):
    """ pylint wants a public reponse method """
    webapp.RequestHandler.__response__(self)

  def get(self):
    """ show the usage string """
    pagecount.IncrPageCount("export.ShowUsage", 1)
    self.response.out.write(USAGE)

def verify_dig_sig(request, caller):
  """ 
  require callers pass param &digsig=[string] such that
  the hash of the string they pass to us equals QT
  """
  digsig = utils.get_last_arg(request, "digsig", "")
  # check the passed &digsig with QT...
  # and work it if they match
  if hashlib.sha512(digsig).hexdigest() != QT:
    pagecount.IncrPageCount("export.%s.noDigSig" % caller, 1)
    raise Fail("no &digsig")

def get_limit(request, caller):
  """ get our limit """
  try:
    limit = int(utils.get_last_arg(request, "limit", "1000"))
  except:
    pagecount.IncrPageCount("export.%s.nonIntLimit" % caller, 1)
    raise Fail("non integer &limit")

  if limit < 1:
    limit = 1000

  return limit

def get_model(table, caller):
  """ get our model """
  if table == "UserInfo":
    model = models.UserInfo
  elif table == "UserStats":
    model = models.UserStats
  elif table == "UserInterest":
    model = models.UserInterest
  elif table == "VolunteerOpportunityStats":
    model = models.VolunteerOpportunityStats
  elif table == "VolunteerOpportunity":
    model = models.VolunteerOpportunity
  elif table == "Config":
    model = config.Config
  elif table == "Posting":
    model = models.Posting
  elif table == "PageCountShard":
    model = pagecount.PageCountShard
  elif table == "TestResults":
    model = helpers.TestResults
  else:
    pagecount.IncrPageCount("export.%s.unknownTable" % caller, 1)
    raise Fail("unknown table name '%s'" % table)

  return model

def get_min_key(table, min_key = "", offset = 0):
  """
  get the next key in our sequence
  or get the lowest key value in the table
  """
  if min_key == "":
    query = table.gql(("ORDER BY __key__ LIMIT %d, 1" % (offset)))
    row = query.get()
  else:
    row = table(key_name = min_key)

  if not row:
    if min_key == "":
      raise Fail("no data in %s" % table)
    else:
      return None

  return row.key()
  
def get_next_key(table, curr_key):
  query = table.gql(("WHERE __key__ > %s LIMIT 0, 2" % key))
  row = query.get()
  return row.key()
  
def get_max_key(table, max_key = ""):
  """
  get the next key in our sequence
  or get the lowest key value in the table
  """
  if max_key == "":
    query = table.gql("ORDER BY __key__ DESC LIMIT 1")
    row = query.get()
  else:
    row = table(key_name = max_key)

  if not row:
    if max_key == "":
      raise Fail("no data in %s" % table)
    else:
      return None

  return row.key()

def export_table_as_tsv(table, min_key, limit):
  """ 
  get rows from this table as TSV
  """
  # neither \t nor \n should appear in the data without
  # being properly escaped in double quotes
  delim, recsep = ("\t", "\n")

  def get_fields(table_object):
    """ get a list of field names prepended with 'key' """
    fields = ["key"]
    for field in table_object.properties():
      fields.append(field)
    return fields

  def field_to_str(value):
    """ get our field value as a string """
    if not value:
      field_value = ""
    else:
      try:
        # could be a key or a Reference object, eg
        #   <models.UserInfo object at 0x94bed32057743898>
        field_value = str(value.key().id_or_name())
      except:
        field_value = str(value)
    return field_value

  def get_header(fields, delim):
    """ get a delimited list of the field names """
    header = delim.join(fields)
    return header

  def esc_value(value, delim, recsep):
    """ make sure our delimiter and record separator are not in the data """
    return field_to_str(value).replace(delim, "\\t").replace(recsep, "\\n")

  fields = get_fields(table)

  output = []
  if min_key == "":
    # this is the first record we output so add the header
    output.append(get_header(fields, delim))
    inequality = ">="
  else:
    inequality = ">"

  done = False
    
  startKey = get_min_key(table, min_key)
  
  lastKey = ""
  processed = 0
  while done == False:  
    try:
      queryString = "WHERE __key__ %s :1 ORDER BY __key__" % inequality
      query = table.gql(queryString,startKey)
    except:
      query = None
      return "query error"
    cnt = 0
    if query:
      rsp = query.fetch(limit)
      cnt = query.count(limit)
      for row in rsp:
        line = []
        for field in fields:
          if field == "key":
            value = row.key().id_or_name()
            lastKey = row.key()
          else:
            value = getattr(row, field, None)
          line.append(esc_value(value, delim, recsep))
        output.append(delim.join(line))
    else:
      output = "query was null..."
    
    inequality = ">"
    startKey = lastKey
    processed += cnt
    if cnt < GQL_MAX_ROWS:
      done = True
    
  return "%s%s" % (recsep.join(output), recsep)

class ExportTableTSV(webapp.RequestHandler):
  """ export the data in the table """
  def __init__(self):
    if hasattr(webapp.RequestHandler, '__init__'):
      webapp.RequestHandler.__init__(self)

  def request(self):
    """ pylint wants a public request method """
    webapp.RequestHandler.__response__(self)

  def response(self):
    """ pylint wants a public response method """
    webapp.RequestHandler.__response__(self)

  def get(self, table):
    """ handle the request to export the table """
    pagecount.IncrPageCount("export.ExportTableTSV.attempt", 1)
    verify_dig_sig(self.request, "ExportTableTSV")
    limit = get_limit(self.request, "ExportTableTSV")
    min_key = utils.get_last_arg(self.request, "min_key", "")
    model = get_model(table, "ExportTableTSV")
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.out.write(export_table_as_tsv(model, min_key, limit))
    pagecount.IncrPageCount("export.ExportTableTSV.success", 1)

def transfer_table(source, destination, min_key, limit):
  """ transfer records from source to destination """
  last_key = ""
  number_of_rows = 0

  def populate_row(src_table, dest_table, row, key = None):
    """ put a row from the src_table into the dest_table """
    if key:
      record = dest_table(key_name = str(key))
    else:
      record = dest_table()

    for field in src_table.properties():
      setattr(record, field, getattr(row, field))

    record.put()

  if min_key == "":
    # this is the first record 
    inequality = ">="
  else:
    inequality = ">"

  query = source.gql(("WHERE __key__ %s :1 ORDER BY __key__" % inequality),
          get_min_key(source, min_key))

  rsp = query.fetch(limit)
  for row in rsp:
    last_key = row.key().id_or_name()
    try:
      # try to preserve our key name
      populate_row(source, destination, row, last_key)
      number_of_rows += 1
    except:
      populate_row(source, destination, row)
      number_of_rows += 1

  return last_key, number_of_rows

def verify_table_name(table_to):
  """ make sure this table name is safe to use """
  good_chars = re.compile(r'[A-Za-z0-9_]')
  good_name = ''.join(c for c in table_to if good_chars.match(c))
  if table_to != good_name:
    pagecount.IncrPageCount("export.TransferTable.badDestName", 1)
    raise Fail("destination contains nonalphanumerics '%s'" % table_to)

class TransferTable(webapp.RequestHandler):
  """ export the data in the table """
  def __init__(self):
    if hasattr(webapp.RequestHandler, '__init__'):
      webapp.RequestHandler.__init__(self)

  def request(self):
    """ pylint wants a public request method """
    webapp.RequestHandler.__response__(self)

  def response(self):
    """ pylint wants a public response method """
    webapp.RequestHandler.__response__(self)

  def get(self, table_from, table_to):
    """ handle the request to replicate a table """
    pagecount.IncrPageCount("export.TransferTable.attempt", 1)
    verify_dig_sig(self.request, "TransferTable")
    limit = get_limit(self.request, "TransferTable")
    min_key = utils.get_last_arg(self.request, "min_key", "")

    if table_from == table_to:
      pagecount.IncrPageCount("export.TransferTable.sameTableName", 1)
      raise Fail("cannot transfer '%s' to itself" % table_from)

    if (table_to[0:len(table_from)] + '_') != (table_from + '_'):
      raise Fail("destination must start with '%s_'" % table_from)

    verify_table_name(table_to)

    # match our type of table
    source = get_model(table_from, "TransferTable")
    destination = type(table_to, (source,), {})

    if min_key == "":
      # a blank key means that we are starting at the top of the table 
      # so we need to clean out anything that may already be in
      # the destination table
      while True:
        query = destination.all()
        # 500 records is the max
        results = query.fetch(500)
        if results:
          db.delete(results)
        else:
          break

    last_key, rows = transfer_table(source, destination, min_key, limit) 
    self.response.out.write("from %s to %s\nrows\t%d\nlast_key\t%s\n"
      % (table_from, table_to, rows, last_key))
    pagecount.IncrPageCount("export.TransferTable.success", 1)

class PopulateTable(webapp.RequestHandler):
  """ populate the data in the table """
  def __init__(self):
    if hasattr(webapp.RequestHandler, '__init__'):
      webapp.RequestHandler.__init__(self)

  def request(self):
    """ pylint wants a public request method """
    webapp.RequestHandler.__response__(self)

  def response(self):
    """ pylint wants a public response method """
    webapp.RequestHandler.__response__(self)

  def post(self, table):
    """ handle the request to populate the table """
    pagecount.IncrPageCount("export.PopulateTable.attempt", 1)
    verify_dig_sig(self.request, "PopulateTable")

    table_version = str(utils.get_last_arg(self.request, "tv", ""))
    if len(table_version) > 0:
      verify_table_name(table_version)
      source = get_model(table, "PopulateTable")
      destination = type(table + table_version, (source,), {})
    else:
      destination = get_model(table, "PopulateTable")

    # handle reference properties
    def ref_property_UserInfo(field):
      rmodel = type('UserInfo' + table_version, (models.UserInfo,), {})
      return rmodel.get_by_key_name(field)

    def nop(v):
      """ this is used for unknown field types """
      return v

    def str_to_datetime(datetimestring):
      """ convert string to a real DateTime object """
      # dont need milliseconds here
      ar = datetimestring.split(".")
      datetime_format = "%Y-%m-%d %H:%M:%S"
      return datetime.strptime(ar[0], datetime_format)

    def str_to_date(datestring):
      """ convert string to a real Date object """
      date_format = "%Y-%m-%d"
      return datetime.strptime(datestring, date_format).date()

    try:
      reset = int(utils.get_last_arg(self.request, "reset", "0"))
    except:
      pagecount.IncrPageCount("export.%s.nonIntLimit" % "PopulateTable", 1)
      raise Fail("invalid &reset signal")

    if reset == 1:
      """ we should only see this with a first batch of records """
      logging.info("export.PopulateTable reset signal recvd for %s%s" 
        % (table, table_version))
      self.response.out.write(
        "PopulateTable: reset signal recvd, clearing all rows\n")
      pagecount.IncrPageCount("export.%s.reset" % "PopulateTable", 1)
      while True:
        query = destination.all()
        # cannot delete more than 500 entities in a single call
        # and if there are a lot here we are going to timeout
        # anyway but better to try and fail than risk duplicating
        results = query.fetch(500)
        if results:
          logging.info("export.PopulateTable deleting %d from %s%s" % 
            (len(results), table, table_version))
          self.response.out.write("PopulateTable: deleting %d from %s%s\n" 
              % (len(results), table, table_version))
          db.delete(results)
        else:
          logging.info("export.PopulateTable %s%s reset complete" % 
            (table, table_version))
          self.response.out.write("PopulateTable: %s%s reset complete\n" % 
            (table, table_version))
          break

    # one record per line
    rows = self.request.get("row").split("\n")

    # the first row is a header
    header = rows.pop(0).split("\t")

    field_type = []
    for field in header:
      # we are going to want to remember a function for each field type
      # but for now all we are doing is initializing the list
      field_type.append(None)
      
    limit = get_limit(self.request, "PopulateTable")
    logging.info("export.PopulateTable write to %s%s" % (table, table_version))

    written = 0
    row_number = 0
    for row in rows:
      row_number += 1
      # all of our kind of lines should start "row="
      if len(row) > ROW_MARKER_LEN and row[0:ROW_MARKER_LEN] == ROW_MARKER:
        fields = row[ROW_MARKER_LEN:].split("\t")
        for i, field in enumerate(fields):
          if i == 0:
            # on the first column (key) we only instantiate our kind of record
            try:
              # it could be a named key
              if not str(field)[0].isdigit():
                record = destination(key_name = str(field))
              else:
                record = destination()
            except:
              record = destination()
          else:
            if field is None or len(strip(field)) < 1:
              # no field/field value, nothing to do
              continue

            if field_type[i] != None:
              # we think we already know what kind of field this is 
              try:
                # but we could be wrong
                setattr(record, header[i], field_type[i](field))
              except:
                # nothing we can really do about it now except carry on
                # and see if we can still make this a good record
                logging.warning(
                  "export.PopulateTable %s = %s not set in row %d of %s%s" % 
                          (header[i], field, row_number, table, table_version))
                self.response.out.write("field %s = %s not set in row %d of %s%s\n" % 
                          (header[i], field, row_number, table, table_version))
                pass
            else:
              # on the first row of the file
              # we dont know what type of field this is
              # but we can try them all until we succeed
              # and remember which one worked for subsequent rows
              n = 0
              while n < MAX_FIELD_TYPES:
                if n == FIELD_TYPE_REF:
                  if table != "UserInterest" or header[i] != "user":
                    continue
                  setattr(record, header[i], ref_property_UserInfo(field))
                  field_type[i] = ref_property_UserInfo
                  break
                elif n == FIELD_TYPE_DATETIME:
                  try:
                    setattr(record, header[i], str_to_datetime(field))
                    field_type[i] = str_to_datetime
                    break
                  except:
                    pass
                elif n == FIELD_TYPE_DATE:
                  try:
                    setattr(record, header[i], str_to_date(field))
                    field_type[i] = str_to_date
                    break
                  except:
                    pass
                elif n == FIELD_TYPE_STR:
                  try:
                    setattr(record, header[i], field)
                    field_type[i] = str
                    break
                  except:
                    pass
                elif n == FIELD_TYPE_BOOL:
                  try:
                    setattr(record, header[i], bool(field))
                    field_type[i] = bool
                    break
                  except:
                    pass
                elif n == FIELD_TYPE_INT:
                  try:
                    setattr(record, header[i], int(field))
                    field_type[i] = int
                    break
                  except:
                    pass
                elif n == FIELD_TYPE_LONG:
                  try:
                    setattr(record, header[i], long(field))
                    field_type[i] = long
                    break
                  except:
                    pass
                elif n == FIELD_TYPE_FLOAT:
                  try:
                    setattr(record, header[i], float(field))
                    field_type[i] = float
                    break
                  except:
                    pass
                n += 1
              if n >= MAX_FIELD_TYPES:
                logging.warning(
                  "export.PopulateTable unknown field type %s in %s%s" % 
                  (header[i], table, table_version))
                self.response.out.write("unknown field type %s in %s%s\n" % 
                  (header[i], table, table_version))
                field_type[i] = nop
              else:
                logging.debug("%s is type %d\n" % (header[i], n))

        # end-of for each field
        try:
          # ready to attempt a put
          record.put()
          written += 1
          if written >= limit:
            break
        except:
          logging.error("export.PopulateTable put failed at row %d in %s%s" % 
            (row_number, table, table_version))
          self.response.out.write("put failed at row %d in %s%s\n" % 
            (row_number, table, table_version))

    # end-of for each row
    logging.info("export.PopulateTable wrote %d rows to %s%s" % 
            (written, table, table_version))
    self.response.out.write("wrote %d rows to %s%s\n" % 
            (written, table, table_version))
    pagecount.IncrPageCount("export.PopulateTable.success", 1)

class ClearTable(webapp.RequestHandler):
  """ clear all data from a table """
  def __init__(self):
    if hasattr(webapp.RequestHandler, '__init__'):
      webapp.RequestHandler.__init__(self)

  def request(self):
    """ pylint wants a public request method """
    webapp.RequestHandler.__response__(self)

  def response(self):
    """ pylint wants a public response method """
    webapp.RequestHandler.__response__(self)

  def get(self, table):
    """ clear data """
    pagecount.IncrPageCount("export.ClearTable", 1)
    verify_dig_sig(self.request, "ClearTable")

    table_version = str(utils.get_last_arg(self.request, "tv", ""))
    if len(table_version) > 0:
      source = get_model(table, "ClearTable")
      destination = type(table + table_version, (source,), {})
    else:
      destination = get_model(table, "ClearTable")

    limit = get_limit(self.request, "ClearTable")
    if limit < 1:
      limit = 500
    elif limit > 500:
      limit = 500

    query = destination.all()
    # cannot delete more than 500 entities in a single call
    results = query.fetch(limit)
    if results:
      self.response.out.write("ClearTable: deleting %d from %s%s\n"
          % (len(results), table, table_version))
      db.delete(results)
    else:
      self.response.out.write("ClearTable: %s%s clear complete\n" % 
            (table, table_version))

"""
TODO:
/exportapi/export/<tablename>
/exportapi/import/<tablename>
/exportapi/clear/<tablename>
/exportapi/transfer/<from-table>/<to-table>
"""
APPLICATION = webapp.WSGIApplication(
    [ ("/export/(.*?)\.tsv", ExportTableTSV),
      ("/export/-/(.*?)", PopulateTable),
      ("/export/-clear-/(.*?)", ClearTable),
      ("/export/(.*?)/(.*?)", TransferTable),
      ("/export/", ShowUsage)
    ], debug=True)

def main():
  """ execution begins """
  run_wsgi_app(APPLICATION)

if __name__ == "__main__":
  main()
