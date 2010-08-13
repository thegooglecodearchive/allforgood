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
geocode client, which uses Google Maps API
"""

import re
import urllib
import logging
import time
from datetime import datetime
from google.appengine.api import urlfetch
from versioned_memcache import memcache

import api

def parse_geo_response(res):
  if "," not in res:
    return 999, 0, 0, 0
  try:
    respcode, zoom, lat, lng = res.split(",")
    return respcode, zoom, lat, lng
  except:
    logging.warning('geocode.geocode unparseable response: ' + res[0:80])
    return 999, 0, 0, 0


def is_latlong(instr):
  """check whether a string is a valid lat-long."""
  return (re.match(r'^\s*[0-9.+-]+\s*,\s*[0-9.+-]+\s*$', instr) != None)
  

def is_latlongzoom(instr):
  """check whether a string is a valid lat-long-zoom."""
  return (re.match(r'^\s*[0-9.+-]+\s*,\s*[0-9.+-]+\s*,\s*[0-9.+-]+\s*$', instr) != None)


def geocode(addr, usecache=True, retrying = False):
  """convert a human-readable address into a "lat,long" value (string)."""
  loc = addr.lower().strip()

  # already geocoded-- just return
  if is_latlongzoom(loc):
    return loc

  if is_latlong(loc):
    # regexp allow missing comma
    # TODO: pick a smart default zoom, depending on population density.
    return loc + ",4"

  loc = re.sub(r'^[^0-9a-z]+', r'', loc)
  loc = re.sub(r'[^0-9a-z]+$', r'', loc)
  loc = re.sub(r'\s\s+', r' ', loc)

  memcache_key = "geocode:" + loc
  val = memcache.get(memcache_key)
  if usecache and val:
    logging.info("geocode: cache hit loc=" + loc + " val=" + val)
    return val

  if not retrying:
    params = urllib.urlencode(
      {'q':loc.lower(), 'output':'csv', 'oe':'utf8', 'sensor':'false', 'gl':'us',
       'key':'ABQIAAAAxq97AW0x5_CNgn6-nLxSrxQuOQhskTx7t90ovP5xOuY'+\
       '_YrlyqBQajVan2ia99rD9JgAcFrdQnTD4JQ'})
    fetchurl = "http://maps.google.com/maps/geo?%s" % params
    logging.info("geocode: cache miss, trying " + fetchurl)
    fetch_result = urlfetch.fetch(fetchurl, deadline = api.CONST_MAX_FETCH_DEADLINE)
    if fetch_result.status_code != 200:
      # fail and also don't cache
      return ""

    res = fetch_result.content
    logging.info("geocode: maps responded %s" % res)
    respcode, zoom, lat, lng = parse_geo_response(res)
    if respcode == '200':
      logging.info("geocode: success " + loc)
      val = lat+","+lng+","+zoom
      memcache.set(memcache_key, val)
      return val

  if retrying or respcode == '620':
    params = urllib.urlencode(
      {'q':loc.lower(), 
      })
    fetchurl = "http://pipes.appspot.com/geo?%s" % params
    fetch_result = urlfetch.fetch(fetchurl, deadline = api.CONST_MAX_FETCH_DEADLINE)
    res = fetch_result.content
    logging.info("geocode: datastore responded %s" % res)
    respcode, zoom, lat, lng = parse_geo_response(res)
    if respcode == '200':
      val = lat+","+lng+","+zoom
      memcache.set(memcache_key, val)
      return val
    if respcode == '620' and not retrying:
      logging.info("geocode: retrying " + loc)
      return geocode(addr, usecache, True)

  logging.info("geocode: failed " + loc)
  return ""
