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

from datetime import datetime
from time import sleep

MAX_WAIT = 6
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


def is_bad_link(url):
  """ """

  rtn = False
  if not url or len(url) < 11 or os.path.isfile(DIR_BAD + get_link_file_name(url)):
    rtn = True
  else:
    if url.lower().startswith('http://localhost'):
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
  if url and url.find('volunteermatch.org') >= 0:
    return 'unchecked currently unverifiable'

  if url and url.find('truist.com') >= 0:
    return 'unchecked currently unverifiable'

  rtn = 'unchecked unknown error'

  file_name = get_link_file_name(url)
  if os.path.isfile(DIR_CHK + file_name):
    rtn = 'checked'
    if not is_bad_link(url):
      last_check = get_file_age(DIR_CHK + file_name)
      # dont need to check again for at least a week
      if last_check < WEEK:
        # unless we insist
        if not recheck:
          return rtn
       
    # clear last results and recheck
    os.remove(DIR_CHK + file_name)
    if os.path.isfile(DIR_BAD + file_name):
      os.remove(DIR_BAD + file_name)

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
