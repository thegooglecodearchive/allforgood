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

MAX_WAIT = 7
USER_AGENT = 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'
DIR_BAD = '/home/footprint/allforgood-read-only/datahub/bad-links/'
DIR_CHK = '/home/footprint/allforgood-read-only/datahub/links/'

HOUR = (3600)
DAY = (24 * HOUR)
WEEK = (7 * DAY)
DELAY = 0.75

def get_link_file_name(url):
  """ """

  return hashlib.md5(url).hexdigest() + '.url'


def get_file_age(file):
  """ """

  stat = os.stat(file)
  mtime = datetime.fromtimestamp(stat.st_mtime)
  delta = datetime.now() - mtime
  return delta.seconds


def is_checked(url, file_name = None):
  """ """
  rtn = False
  if not file_name:
    file_name = get_link_file_name(url)

  if os.path.isfile(DIR_CHK + file_name):
    rtn = True

  return rtn


def is_marked_bad(url, file_name = None):
  """ """
  rtn = False
  if not file_name:
    file_name = get_link_file_name(url)

  if os.path.isfile(DIR_BAD + file_name):
    rtn = True

  return rtn


def mark_bad(url, rtn, file_name = None):
  """ """

  if not file_name:
    file_name = get_link_file_name(url)

  fh = open(DIR_BAD + file_name, 'w')
  if fh:
    if rtn.find('\t' + url) >= 0:
      fh.write(rtn + '\n')
    else:
      fh.write(rtn + '\t' + url + '\n')
    fh.close()


def mark_checked(url, rtn, file_name = None):
  """ """

  if not file_name:
    file_name = get_link_file_name(url)

  fh = open(DIR_CHK + file_name, 'w')
  if fh:
    if rtn.find('\t' + url) >= 0:
      fh.write(rtn + '\n')
    else:
      fh.write(rtn + '\t' + url + '\n')
    fh.close()

  return rtn

  

def is_bad_link(url, recheck = False):
  """ """

  rtn = False
  if not url or len(url) < 11 or url.lower().find('localhost') >= 0:
    rtn = True
  else:
    file_name = get_link_file_name(url)
    if not is_checked(url, file_name) or recheck:
      rsp = check_link(url, recheck, file_name)
      if rsp.startswith('bad'):
        rtn = True

  return rtn


def check_link(url, recheck = False, file_name = None):
  """ """

  rtn = 'unchecked '
  if url.find('volunteermatch.org') >= 0:
    # jsp shows head requests a 404
    return rtn + url

  if url.find('idealist.org') >= 0:
    # login required, shows head requests a 401
    return rtn + url

  if not file_name:
    file_name = get_link_file_name(url)

  if is_checked(url, file_name):
    rtn = 'checked'
    last_check = get_file_age(DIR_CHK + file_name)
    if is_marked_bad(url, file_name) and (last_check > WEEK or (recheck and last_check > DAY)):
      os.remove(DIR_BAD + file_name)
    else:
      # dont need to check again for at least a week to 10 days
      # random so we dont hit every single link on the same day
      if not recheck and last_check < (WEEK + (DAY * random.choice([0, 1, 2, 3]))):
        return rtn

  rtn = 'unchecked unknown error'

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
    rtn = 'bad: could not connect\t' + url

  if connection:
    try:
      connection.request('HEAD', url_d.path, urllib.urlencode(params), headers)
    except:
      socket.setdefaulttimeout(default_timeout)
      rtn = 'bad: could not req response from\t' + url

  if connection:
    try:
      rsp = connection.getresponse()
    except:
      socket.setdefaulttimeout(default_timeout)
      rtn = 'bad: could not get response from\t' + url

  socket.setdefaulttimeout(default_timeout)

  if not rsp:
    mark_bad(url, rtn, file_name)
  else:
    rtn = str(rsp.status)
    if not rsp.status in [200, 301, 302]:
      # special case
      if rsp.status == 404 and url.find('createthegood') >= 0:
        rtn = 'maybe: ' + rtn 
      else:
        rtn = 'bad: ' + rtn
        mark_bad(url, rtn, file_name)

  mark_checked(url, rtn, file_name)

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
