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
"""Exports TSV data over HTTP.

Usage:
  %s [flags]

    --url=<string>      URL endpoint to get exported data. (Required)
    --batch_size=<int>  Number of Entity objects to include in each post to
                        smaller the batch size should be. (Default 1000)
    --filename=<path>   Path to the TSV file to export. (Required)
    --digsig=<string>   value passed to endpoint permitting export

The exit status will be 0 on success, non-zero on failure.
"""

import sys
import re
import logging
import getopt
import urllib2
import datetime

def PrintUsageExit(code):
  print sys.modules['__main__'].__doc__ % sys.argv[0]
  sys.stdout.flush()
  sys.stderr.flush()
  sys.exit(code)

def Pull(filename, url, min_key, delim, prefix):
  # get content from url and write to filename
  try:
    connection = urllib2.urlopen(url);
    # TODO: read 100 lines incrementally and show progress
    content = connection.read()
    connection.close()
  except urllib2.URLError, e:
    logging.error('%s returned error %i, %s' % (url, e.code, e.msg))
    sys.exit(2)

  try:
    tsv_file = file(filename, 'a')
  except IOError:
    logging.error("I/O error({0}): {1}".format(errno, os.strerror(errno)))
    sys.exit(3)

  if prefix:
    lines = content.split("\n")
    lines.pop()
    content = ("%s" % prefix) + ("\n%s" % prefix).join(lines) + "\n"

  tsv_file.write(content)
  tsv_file.close()

  # count the number of lines
  list = content.splitlines()
  line_count = len(list)
  last_line = list[line_count - 1]
  if min_key == "":
    # that's our header, don't count it
    line_count -= 1

  # get the key value of the last line
  fields = last_line.split(delim)
  min_key = fields[0][4:]

  return min_key, line_count

def ParseArguments(argv):
  opts, args = getopt.getopt(
    argv[1:],
    'dh',
    ['debug', 'help', 
     'url=', 'filename=', 'prefix=', 'digsig=', 'batch_size='
    ])

  url = None
  filename = None
  digsig = ''
  prefix = ''
  batch_size = 1000

  for option, value in opts:
    if option == '--debug':
      logging.getLogger().setLevel(logging.DEBUG)
    if option in ('-h', '--help'):
      PrintUsageExit(0)
    if option == '--url':
      url = value
    if option == '--filename':
      filename = value
    if option == '--prefix':
      prefix = value
    if option == '--digsig':
      digsig = value
    if option == '--batch_size':
      batch_size = int(value)
      if batch_size <= 0:
        print >>sys.stderr, 'batch_size must be 1 or larger'
        PrintUsageExit(1)

  return (url, filename, batch_size, prefix, digsig)

def main(argv):
  logging.basicConfig(
	level=logging.INFO,
	format='%(levelname)-8s %(asctime)s %(message)s')

  args = ParseArguments(argv)
  if [arg for arg in args if arg is None]:
    print >>sys.stderr, 'Invalid arguments'
    PrintUsageExit(1)

  url, filename, batch_size, prefix, digsig = args

  delim = "\t"
  min_key = ""
  lines = batch_size + 2
  while lines >= batch_size:
    url_step = ("%s?digsig=%s&min_key=%s&limit=%s" %
                 (url, str(digsig), str(min_key), str(batch_size)))
    if min_key != "":
      log_key = min_key
    else:
      log_key = "[start]"
    t0 = datetime.datetime.now()
    min_key, lines = Pull(filename, url_step, min_key, delim, prefix)
    #print min_key
    diff = datetime.datetime.now() - t0
    secs = "%d.%d" % (diff.seconds, diff.microseconds/1000)
    logging.info('fetched header + %d in %s secs from %s', lines, secs, log_key)

  return 0

if __name__ == '__main__':
  sys.exit(main(sys.argv))

