#!/usr/bin/env python
#
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
#
"""Creates backup of tables.
"""

import sys
import logging
import getopt
import urllib2
import datetime
from datetime import date

def print_usage_exit(code):
  """ print usage and exit """
  print sys.modules['__main__'].__doc__ % sys.argv[0]
  sys.stdout.flush()
  sys.stderr.flush()
  sys.exit(code)

def handle_response(url):
  """ read the last key and the number of records copied """
  try:
    connection = urllib2.urlopen(url)
    content = connection.read()
    connection.close()
  except urllib2.URLError, eobj:
    logging.error('%s returned error %i, %s' % (url, eobj.code, eobj.msg))
    sys.exit(2)

  last_key = ""
  rows = 0
  lines = content.split("\n")
  for line in lines:
    field = line.split("\t")
    if field[0] == "rows":
      rows = int(field[1])
    elif field[0] == "last_key":
      last_key = field[1]

  return last_key, rows

def parse_arguments(argv):
  """ parse arguments """
  opts, args = getopt.getopt(
    argv[1:],
    'dh',
    ['debug', 'help', 'url=', 'table=',
     'backup_version=', 'restore_version=', 'digsig=', 'batch_size='
    ])

  def lzero(number_string):
    """ prepend 0 if length less than 2 """
    rtn = number_string
    while len(rtn) < 2:
      rtn = '0' + rtn
    return rtn

  url = "http://footprint2009dev.appspot.com/export"
  table = ''
  tod = date.today()
  backup_version = str(tod.year) + lzero(str(tod.month)) + lzero(str(tod.day))
  restore_version = ''
  digsig = ''
  batch_size = 1000

  for option, value in opts:
    if option == '--debug':
      logging.getLogger().setLevel(logging.DEBUG)
    if option in ('-h', '--help'):
      print_usage_exit(0)
    if option == '--url':
      url = value
    if option == '--backup_version':
      backup_version = value
      if restore_version:
        print >> sys.stderr, 'backup and restore are mutually exclusive'
        print_usage_exit(1)
    if option == '--restore_version':
      restore_version = value
      if backup_version:
        print >> sys.stderr, 'backup and restore are mutually exclusive'
        print_usage_exit(1)
    if option == '--table':
      table = value
    if option == '--digsig':
      digsig = value
    if option == '--batch_size':
      batch_size = int(value)
      if batch_size <= 0:
        print >> sys.stderr, 'batch_size must be 1 or larger'
        print_usage_exit(1)

  opts = args # because pylint said args was unused
  return (url, table, backup_version, restore_version, batch_size, digsig)

def main(argv):
  """ start here """
  logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)-8s %(asctime)s %(message)s')

  args = parse_arguments(argv)
  if [arg for arg in args if arg is None]:
    print >> sys.stderr, 'Invalid arguments'
    print_usage_exit(1)

  base_url, table, backup_version, restore_version, batch_size, digsig = args
  if not base_url:
    print >> sys.stderr, 'specify url'
    print_usage_exit(1)

  if backup_version:
    url = "%s/%s/%s_%s" % (base_url, table, table, backup_version)
  elif restore_version:
    url = "%s/%s_%s/%s" % (base_url, table, table, restore_version)
  else:
    print >> sys.stderr, 'specify either backup_version or restore_version'
    print_usage_exit(1)

  min_key = ''
  lines = batch_size
  while lines == batch_size:
    url_step = ("%s?digsig=%s&min_key=%s&limit=%s" %
                 (url, str(digsig), str(min_key), str(batch_size)))

    if min_key != "":
      log_key = min_key
    else:
      log_key = "[start]"
    start_time = datetime.datetime.now()
    min_key, lines = handle_response(url_step)
    diff = datetime.datetime.now() - start_time
    secs = "%d.%d" % (diff.seconds, diff.microseconds/1000)
    logging.info('fetched %d in %s secs from %s', lines, secs, log_key)

  return 0

if __name__ == '__main__':
  sys.exit(main(sys.argv))
