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
import urllib2
import logging

import hashlib
import hmac
import base64

import simplejson as json

import time
from datetime import datetime
from google.appengine.api import urlfetch
from google.appengine.ext import db

from versioned_memcache import memcache

import api
import private_keys

ACCURACY = { "ROOFTOP" : 5, # precise geocode accurate down to street address
             "RANGE_INTERPOLATED" : 4, # an approximation interpolated between two precise points 
             "GEOMETRIC_CENTER" : 3, # geometric center of a result such as a polyline 
             "APPROXIMATE" : 2, # indicates that the returned result is approximate.
           }

class RevGeo(db.Model):
  """ key = lat.###,lng.### """
  json = db.TextProperty()


def parse_geo_response(res):
  
  jo = None
  try:
    jo = json.loads(res.encode('ascii', 'xmlcharrefreplace'))
  except:
    logging.warning('geocode.geocode unparseable response: ' + res[0:80])
    return 999, 0, 0, 0

  if jo:
    rsp = jo.get('status', 'Unknown error')
    if rsp != 'OK':
      logging.warning('geocode response: ' + rsp)
    else:
      jo_results = jo.get('results', None)[0]
      if jo_results:
        jo_geo = jo_results.get('geometry', None)
        if jo_geo:
          zoom = str(ACCURACY.get(jo_geo.get('location_type', None), "0"))
          jo_loc = jo_geo.get('location', None)
          if jo_loc:
            lat = str(jo_loc.get('lat', "0"))
            lng = str(jo_loc.get('lng', "0"))
            return '200', zoom, lat, lng

  logging.warning('geocode.geocode unparseable response: ' + res[0:80])
  return 999, 0, 0, 0


def is_latlong(instr):
  """check whether a string is a valid lat-long."""
  return (re.match(r'^\s*[0-9.+-]+\s*,\s*[0-9.+-]+\s*$', instr) != None)
  

def is_latlongzoom(instr):
  """check whether a string is a valid lat-long-zoom."""
  return (re.match(r'^\s*[0-9.+-]+\s*,\s*[0-9.+-]+\s*,\s*[0-9.+-]+\s*$', instr) != None)


def sign_maps_api_request(url):

  key = base64.urlsafe_b64decode(private_keys.MAPS_API_PRIVATE_KEY)
  signature = hmac.new(key, url, hashlib.sha1)
  return base64.urlsafe_b64encode(signature.digest())


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
      {'address':loc.lower(), 
       'sensor':'false', 
       'region':'us',
       'client':private_keys.MAPS_API_CLIENT_ID
      })

    request = "/maps/api/geocode/json?%s" % params
    signature = sign_maps_api_request(request)
    fetchurl = "http://maps.googleapis.com" + request + "&signature=" + signature 
    logging.info("geocode: cache miss, trying " + fetchurl)

    fetch_result = urlfetch.fetch(fetchurl, deadline = api.CONST_MAX_FETCH_DEADLINE)
    if fetch_result.status_code != 200:
      # fail and also don't cache
      logging.info("gecode: fail %s %s" % (str(fetch_result.status_code), fetch_result.content))
      return ""

    res = fetch_result.content
    respcode, zoom, lat, lng = parse_geo_response(res)
    if respcode == '200':
      logging.info("geocode: success " + loc)
      val = lat + "," + lng + "," + zoom
      rev_geocode_json(lat, lng)
      memcache.set(memcache_key, val)
      return val

  logging.info("geocode: failed " + loc)
  return ""


def rev_geocode_json(lat, lng):
  """ """

  jo = None
  json_str = ''

  try:
    lat = float(lat)
    lng = float(lng)
  except:
    logging.warning('geocode: rev_geocode_json given ' + str(lat) + ',' + str(lng))
    return jo
    
  # see if we have a record of this
  db_key = str(round(float(lat) * 1000.0)/1000.0) + ',' + str(round(float(lng) + 1000.0)/1000.0)
  rec = RevGeo.get_by_key_name(db_key)
  if rec:
    json_str = rec.json
  else:
    # try the pipeline cache
    try:
      lat_str = str(round(float(lat) * 1000.0)/1000.0).replace('.', '_').rstrip('0')
      lng_str = str(round(float(lng) + 1000.0)/1000.0).replace('.', '_').rstrip('0')
    except:
      # most likely given junk lat/lng
      return jo

    url = private_keys.NODE2 + '/~footprint/revgeo/G' + 'lat' + lat_str + 'lng' + lng_str + '.json'
    try:
      fh = urllib2.urlopen(url)
      json_str = fh.read()
      fh.close()
      jo = json.loads(json_str.encode('ascii', 'xmlcharrefreplace'))
    except:
      json_str = ''

    if not json_str:
      # try Maps API
      latlng = str(lat) + ',' + str(lng)
      params = urllib.urlencode({'latlng':latlng, 
                                 'sensor':'false', 
                                 'client':private_keys.MAPS_API_CLIENT_ID})
      request = "/maps/api/geocode/json?%s" % params
      signature = sign_maps_api_request(request)
      fetchurl = "http://maps.googleapis.com" + request + "&signature=" + signature
      url = 'http://maps.googleapis.com' + request + '&signature=' + signature
      try:
        fh = urllib2.urlopen(url)
        json_str = fh.read()
        fh.close()
      except:
        return jo

  if json_str:
    if not jo:
      try:
        jo = json.loads(json_str.encode('ascii', 'xmlcharrefreplace'))
      except:
        return jo

    if jo['status'] == 'OK' or jo['status'] == 'ZERO_RESULTS':
      if not rec:
        try:
          rec = RevGeo.get_or_insert(db_key)
          rec.json = json_str
          rec.put()
        except:
          pass

  return jo


def get_statewide(lat, lng):
  """ """

  rtn = 'CA'
  country = 'US'

  jo = rev_geocode_json(lat, lng)
  if jo:
    try:
      if jo['status'] != 'OK':
        logging.warning('geocode.get_statewide: rev_geo says ' + jo['status'])
      else:
        for d in jo['results'][0]['address_components']:
          if 'administrative_area_level_1' in d['types']:
            rtn = d['short_name']
          elif 'country' in d['types']:
            country = d['short_name']
    except:
      logging.warning('geocode.get_statewide: rev_geo call failed')

  if country and country != 'US':
     rtn += '-' + country

  return rtn, country

