#!/usr/bin/python

import os
import sys
import socket
import cgi
import re
import urlparse
import hashlib
import httplib
import urllib
import random

from datetime import datetime
from time import sleep

MAX_WAIT = 3
USER_AGENT = 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'
DIR_BAD = 'bad-links/'
DIR_CHK = 'links/'

HOUR = (3600)
DAY = (24 * HOUR)
WEEK = (7 * DAY)
DELAY = 0.75

def get_link_file_name(url):
  """ """

  return hashlib.md5(url).hexdigest() + '.url'


def is_bad_link(url, recheck = False):
  """ """

  rtn = False
  if not url or len(url) < 11 or url.lower().find('localhost') >= 0:
    rtn = True
  else:
    if os.path.isfile(DIR_BAD + get_link_file_name(url)):
      if not recheck:
        rtn = True
      else:
        rsp = check_link(url)
        if rsp.startswith('bad'):
          rtn = True

  return rtn


def get_file_age(file):
  """ """

  stat = os.stat(file)
  mtime = datetime.fromtimestamp(stat.st_mtime)
  delta = datetime.now() - mtime
  return delta.seconds


def check_link(url, recheck = False):
  """ """

  #http://getinvolved.volunteermatch.org/
  if url:
    if url.find('volunteermatch.org') >= 0:
      return 'unchecked currently unverifiable'

    if url.find('truist.com') >= 0:
      return 'unchecked currently unverifiable'

  file_name = get_link_file_name(url)
  if os.path.isfile(DIR_CHK + file_name):
    rtn = 'checked'
    if is_bad_link(url):
      if os.path.isfile(DIR_BAD + file_name):
        os.remove(DIR_BAD + file_name)
      else:
        last_check = get_file_age(DIR_CHK + file_name)
        # a week to 10 days, random so we dont hit lots on the anniversary
        if last_check < (WEEK + (DAY * random.choice([0, 1, 2, 3]))):
          # dont need to check again for at least a week
          if not recheck:
            # unless we insist
            return rtn
       
    # clear last results and recheck
    os.remove(DIR_CHK + file_name)

  rtn = 'unchecked unknown error'
  if not os.path.isfile(DIR_CHK + file_name):
    fh = open(DIR_CHK + file_name, 'w')
    if fh:
      fh.write(url + '\n')
      fh.close()

    url_d = urlparse.urlparse(url)

    params = cgi.parse_qs(urlparse.urlsplit(url).query)
    headers = {'User-Agent':USER_AGENT}
    default_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(MAX_WAIT)

    rsp = None
    connection = None
    try:
      connection = httplib.HTTPConnection(url_d.netloc)
    except:
      rtn = 'could not connect to %s' % (str(url_d.netloc))

    if connection:
      try:
        connection.request('HEAD', url_d.path, urllib.urlencode(params), headers)
      except:
        socket.setdefaulttimeout(default_timeout)
        rtn = 'could not req response from %s, %s, %s' % (str(url_d.netloc), str(url_d.path), str(params))

    if connection:
      try:
        rsp = connection.getresponse()
      except:
        socket.setdefaulttimeout(default_timeout)
        rtn = 'could not get response from ' + url

    socket.setdefaulttimeout(default_timeout)

    if rsp:
      rtn = str(rsp.status)

    if not rsp or not rsp.status in [200, 301, 302]:
      if rsp and rsp.status == 404 and url.find('createthegood') >= 0:
        rtn = 'maybe:' + rtn 
      else:
        rtn = 'bad: ' + rtn
        fh = open(DIR_BAD + file_name, 'w')
        if fh:
          fh.write(rtn + '\t' + url + '\n')
          fh.close()

  return rtn


def main():

  if not sys.argv[1:]:
    for line in sys.stdin:
      url = line.strip()
      if url:
        if not url.lower().startswith('http'):
          url = 'http://' + url
        rsp = check_link(url)
        print rsp + '\t' + url
        if rsp.find('checked') < 0:
          sleep(DELAY)
  else:
    for arg in sys.argv[1:]:
      if arg:
        url = arg.strip()
        if url:
          if not url.lower().startswith('http'):
            url = 'http://' + url
          print check_link(url, True) + '\t' + url

if __name__ == "__main__":
  main()
