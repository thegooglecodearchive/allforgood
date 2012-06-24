#!/usr/bin/python
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
Geocoder and address functions for backend, using Google Maps API.
"""
import os
import re
import time
import json
import urllib
import urllib2
import xml_helpers as xmlh
from datetime import datetime

#API_KEY = "ABQIAAAAxq97AW0x5_CNgn6-nLxSrxQuOQhskTx7t90ovP5xOuY_YrlyqBQajVan2ia99rD9JgAcFrdQnTD4JQ"
CLIENT_ID = "gme-craigslistfoundation"

# Show status messages (also applies to xml parsing)
SHOW_PROGRESS = False
# Show detailed debug messages (just for the geocoder)
GEOCODE_DEBUG = False
def print_debug(msg):
  """print debug message."""
  if GEOCODE_DEBUG:
    print datetime.now(), msg


def normalize_cache_key(query):
  """Simplifies the query for better matching in the cache."""
  # tnrfv: tab, newline, carriage return, form feed, vertical tab
  query = re.sub(r'\\[tnrfv]', r' ', query)
  # multiple spaces to single space
  query = re.sub(r'\s\s+', r' ', query)
  # lower case, strip spaces from beginning and end
  query = query.lower().strip()
  return query


def filter_cache_delimiters(s):
  for delim in (r'\n', r'\|', r';'):
    s = re.sub(delim, r' ', s)
  return s

GEOCODE_CACHE = None
GEOCODE_CACHE_FN = "geocode_cache.txt"
def geocode(query):
  """Looks up a location query using GMaps API with a local cache and
  returns: address, latitude, longitude, accuracy (as strings).  On
  failure, returns False.

  Accuracy levels:
  7-9 = street address, 6 = road, 5 = zip code
  4 = city, 3 = county, 2 = state, 1 = country"""
  global GEOCODE_CACHE

  query = filter_cache_delimiters(query)

  # load the cache
  if GEOCODE_CACHE == None:
    GEOCODE_CACHE = {}
    geocode_fh = open(GEOCODE_CACHE_FN, "r")
    try:
      for line in geocode_fh:
        # Cache line format is:
        #   query|address;latitude;longitude;accuracy
        # For example:
        #   ca|California;36.7782610;-119.4179324;2
        # Or, if the location can't be found:
        #   Any city anywhere|
        if "|" in line:
          key, result = line.strip().split("|")
          key = normalize_cache_key(key)
          if ";" in result:
            result = tuple(result.split(";"))
          else:
            result = False
          GEOCODE_CACHE[key] = result

          #if GEOCODE_DEBUG:
          #  if len(GEOCODE_CACHE) % 250 == 0:
          #    print_debug("read " + str(len(GEOCODE_CACHE)) + " geocode cache entries.")
    finally:
      geocode_fh.close()

  # try the cache
  key = normalize_cache_key(query)
  if key in GEOCODE_CACHE:
    return GEOCODE_CACHE[key]

  # call Google Maps API
  result = geocode_call(query)
  #print_debug("geocode result: " + str(result))
  if result == False:
    return False  # do not cache

  # cache the result
  if result == None:
    result = False
    cacheline = query + "|"
  else:
    result = map(filter_cache_delimiters, result)
    cacheline = query + "|" + ";".join(result)

  geocode_fh = open(GEOCODE_CACHE_FN, "a")
  xmlh.print_progress("storing cacheline: "+cacheline, "", SHOW_PROGRESS)
  geocode_fh.write(cacheline + "\n")
  geocode_fh.close()

  GEOCODE_CACHE[key] = result
  return result


def geocode_call(query, retries=4):
  """Queries the Google Maps geocoder and returns: address, latitude,
  longitude, accuracy (as strings).  Returns None if the query is
  invalid (result can be cached).  Returns False on error (do not
  cache)."""
  if retries < 0:
    print_debug("geocoder retry limit exceeded")
    return False

  params = urllib.urlencode({'q' : query, 
                             'output' : 'xml',
                             'oe' : 'utf8', 
                             'gl' : 'us', 
                             'sensor' : 'false', 
                             'clientID' : CLIENT_ID})
  try:
    maps_fh = urllib2.urlopen("http://maps.google.com/maps/geo?%s" % params)
    res = maps_fh.read()
    maps_fh.close()
  except IOError, err:
    print_debug("geocode_call: Error contacting Maps API. Sleeping. " + str(err))
    time.sleep(1)
    return geocode_call(query, retries - 1)

  #print_debug("response length: "+str(len(res)))
  if re.search(r'403 Forbidden', res):
    respcode = 403
  else:
    node = xmlh.simple_parser(res, [], False)
    respcode = xmlh.get_tag_val(node, "code")
    if respcode == "":
      #print_debug("unparseable response: "+res)
      return False

  respcode = int(respcode)
  if respcode in (400, 601, 602, 603):  # problem with the query
    return None

  if respcode in (403, 500, 620):  # problem with the server
    print_debug("geocode_call: Connection problem or quota exceeded.  Sleeping...")
    if retries == 4:
      xmlh.print_progress("geocoder: %d" % respcode, "", SHOW_PROGRESS)
    time.sleep(5)
    return geocode_call(query, retries - 1)

  if respcode != 200:
    return False

  # TODO(danyq): if the query is a lat/lng, find the city-level
  # address, not just the first one.
  addr = xmlh.get_tag_val(node, "address")

  # TODO(danyq): Return street/city/country fields separately so that
  # the frontend can decide what to display.  For now, this hack just
  # removes "USA" from all addresses.
  addr = re.sub(r', USA$', r'', addr)
  coords = xmlh.get_tag_val(node, "coordinates")
  if coords == "":
    coords = "0.0,0.0,0"

  # Note the order: maps API returns "longitude,latitude,altitude"
  lng, lat = coords.split(",")[:2]
  accuracy = xmlh.get_tag_attr(node, "AddressDetails", "Accuracy")
  if accuracy == "":
    accuracy = "0"

  return (addr, lat, lng, accuracy)


def rev_geocode_json(lat, lng, key = None, retries = 0, msgd = {}):
  """ """

  jo = None
  if not key:
    try:
      if float(lat) < 0:
        ns = 'S'
      else:
        ns = 'N'
      if float(lng) < 0:
        ew ='E'
      else:
        ew = 'W'

      lat_str = ns + str(round(abs(float(lat)) * 10000.0)/10000.0).replace('.', '_').rstrip('0')
      lng_str = ew + str(round(abs(float(lng)) * 10000.0)/10000.0).replace('.', '_').rstrip('0')
    except:
      # most likely given junk lat/lng
      return jo

    key = 'revgeo/G' + 'lat' + lat_str + 'lng' + lng_str + '.json'
    if 'OVER_QUERY_LIMIT' in msgd and not os.path.isfile(key):
      lat_str = str(round(float(lat) * 10000.0)/10000.0).replace('.', '_').rstrip('0')
      lng_str = str(round(float(lng) + 10000.0)/10000.0).replace('.', '_').rstrip('0')
      key = 'revgeo/' + 'lat' + lat_str + 'lng' + lng_str + '.json'

  if key:
    try:
      fh = open(key, 'r')
      json_str = fh.read()
      fh.close()
      try:
        jo = json.loads(json_str.encode('ascii', 'xmlcharrefreplace'))
        return jo
      except:
        print_debug("rev_geocode_json: could not loads cached " + key)
    except:
      # not cached
      pass
  
  latlng = str(lat) + ',' + str(lng)
  url = "http://maps.googleapis.com/maps/api/geocode/json"
  params = urllib.urlencode({'latlng':latlng, 'sensor':'false', 'clientID':CLIENT_ID})

  json_str = ""
  try:
    fh = urllib2.urlopen("%s?%s" % (url, params))
    json_str = fh.read()
    fh.close()
    retries = 0
  except IOError, err:
    print_debug("rev_geocode_json: error contacting Maps API. Sleeping. " + str(err))
    if retries < 2:
      retries += 1
      time.sleep(1)
      return rev_geocode_json(lat, lng, key, retries)

  if json_str:
    try:
      jo = json.loads(json_str.encode('ascii', 'xmlcharrefreplace'))
    except:
      print_debug("rev_geocode_json: could not loads " + key)

    if jo:
      if jo['status'] == 'OK' or jo['status'] == 'ZERO_RESULTS':
        try:
          fh = open(key, 'w')
          fh.write(json_str)
          fh.close()
        except:
          print_debug("rev_geocode_json: could not cache " + key)

      elif jo['status'] == 'OVER_QUERY_LIMIT':
        print_debug("rev_geocode_json: OVER_QUERY_LIMIT " + key)

  return jo

