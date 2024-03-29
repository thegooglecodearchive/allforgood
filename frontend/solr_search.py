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
low-level routines for querying SOLR and processing the results.
Please don't call this directly-- instead call search.py
"""

import sys
import datetime
import logging
import re
import time
import traceback
import urllib
import random
import math

from django.utils import simplejson
#from versioned_memcache import memcache
from google.appengine.api import memcache
from google.appengine.api import urlfetch
from copy import deepcopy
from operator import itemgetter

import api
import apiwriter
import geocode_mapsV3 as geocode
import ical_filter
import models
import modelutils
import posting
import private_keys
import categories
import searchresult
import utils
import ga
import gzip
from iso8601 import parse_date

from StringIO import StringIO
from boosts import *

RESULT_CACHE_TIME = 900 # seconds
RESULT_CACHE_KEY = 'searchresult:'
KEYWORD_GLOBAL = ""
GEO_GLOBAL = ""
STATEWIDE_GLOBAL = ""
NATIONWIDE_GLOBAL = "US"
PROVIDER_GLOBAL = ""
FULL_QUERY_GLOBAL = ""
DATE_QUERY_GLOBAL = ""
BACKEND_GLOBAL = ""

# Date format pattern used in date ranges.
DATE_FORMAT_PATTERN = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')

# max number of results to ask from SOLR (for latency-- and correctness?)
MAX_RESULTS = 1000

MILES_PER_DEG = 69
DEFAULT_VOL_DIST = 75

def apply_boosts(args, original_query = None):

  def bqesc(s):
    # replace "+ signs" with %2B and spaces with "+ signs", leave else alone
    # maybe like urllib.quote_plus(s.replace('+', '%2B'), '^()[]:*-')
    s = s.strip()
    if s[0] != '(':
      s = '(' + s + ')'
    return s.replace('+', '%2B').replace(' ', '+')

  boost = ''
  for idx, bq in enumerate(DEFAULT_BOOSTS):
    if idx > 0:
      boost += '%20OR%20'
    boost += bqesc(bq)

  if api.PARAM_KEY in args:
    if args[api.PARAM_KEY] in API_KEY_BOOSTS:
      if boost != '&bq=':
        boost += '%20OR%20'
      boost += bqesc(API_KEY_BOOSTS[args[api.PARAM_KEY]])

  if original_query:
    for k, b in CATEGORY_BOOSTS.items():
      if original_query.find(k) >= 0:
        if boost != '&bq=':
          boost += '%20OR%20'
        boost += bqesc(b)
  
  if boost:
    boost = '&bq=(' + boost + ')'
   
  return boost


def apply_api_key_query(q, api_key):
  """ api key based query """ 
  rtn = q

  if api_key in API_KEY_QUERIES:
    rtn = '(%s) AND (%s)' % (q, API_KEY_QUERIES[api_key])
    
  if rtn != q:
    logging.info(q + '|' + str(api_key) + '|' + rtn)

  return rtn


def apply_category_query(q):
  """ in &q= category: may be short hand for a real query """ 

  rtn = q
  for tag, cq in CATEGORY_QUERIES.items():
    rtn = rtn.replace(tag, cq)
    
  return rtn.replace('category:', '')


def apply_filter_query(api_key, args):
  """ """

  rtn = ''
  for fq in FILTER_QUERIES:
    rtn += '&fq=' + urllib.quote_plus(fq)

  for k,fq in API_KEY_FILTER_QUERIES.items():
    if k == api_key:
      rtn += '&fq=' + urllib.quote_plus(fq)

  for k,fq in API_KEY_NEGATED_FILTER_QUERIES.items():
    if k != api_key:
      rtn += '&fq=' + urllib.quote_plus(fq)

  given_query = args.get(api.PARAM_Q, '')
  
  if not args.get(api.PARAM_INVITATIONCODE, '') and args.get(api.PARAM_KEY, '') == "exelis":
    rtn += '&fq=' + urllib.quote_plus('(invitationcode:Exelis OR (*:* AND -invitationcode:[* TO *]))')
  elif not args.get(api.PARAM_INVITATIONCODE, ''):
    rtn += '&fq=' + urllib.quote_plus('-invitationcode:[* TO *]')
  else:
    rtn += '&fq=' + urllib.quote_plus('invitationcode_str:' + args.get(api.PARAM_INVITATIONCODE, ''))

  return rtn


def add_range_filter(field, min_val, max_val):
  """ Convert colons in the field name and build a range specifier
  in SOLR query syntax"""
  result = ' AND '
  result += field
  result += ':[' + str(min_val) + ' TO ' + str(max_val) + ']'
  return result


def rewrite_query(query_str, api_key = None):
  """ Rewrites the query string from an easy to type and understand format
  into a Solr-readable format"""

  query_str = apply_api_key_query(query_str, api_key)

  # Lower-case everything and make boolean operators upper-case, so they
  # are recognized by SOLR.
  # TODO: Don't lowercase field names.
  rewritten_query = query_str.lower()
  rewritten_query = rewritten_query.replace(' or ', ' OR ')
  rewritten_query = rewritten_query.replace(' and ', ' AND ')
  rewritten_query = rewritten_query.replace(' to ', ' TO ')
  
  # 2011-01-17T00:00:00.000Z is a valid date string
  # but 2011-01-17t00:00:00.000z is not
  def reupcase(match_obj):
    return match_obj.group(0).upper()

  rewritten_query = re.sub(r'[0-9]t[0-9]', reupcase, rewritten_query)
  rewritten_query = re.sub(r'[0-9]z', reupcase, rewritten_query)

  # Replace the category filter shortcut with its proper name.
  rewritten_query = rewritten_query.replace('category:', 'categories:')

  return rewritten_query


def get_solr_backend(args):

  # set the solr instance we need to use if not given as an arg
  if api.PARAM_BACKEND_URL not in args:
    # hr = datetime.datetime.now().hour
    hr = float(datetime.datetime.now().hour) + (float(datetime.datetime.now().minute)/60)
    if hr >= 23.5 or hr < 5.5 or (hr >= 11.5 and hr < 17.5):
      # node 1 process at 6, 18
      # node 1 serves at 0, 12
      args[api.PARAM_BACKEND_URL] = private_keys.NODE1_DEFAULT_BACKEND_URL
    else:
      # node 2 process at 0, 12
      # node 2 serves at 6, 18
      args[api.PARAM_BACKEND_URL] = private_keys.NODE2_DEFAULT_BACKEND_URL

    if private_keys.DEFAULT_TO_DEVELOPMENT_NODE:
      args[api.PARAM_BACKEND_URL] = private_keys.NODE3_DEFAULT_BACKEND_URL

  global BACKEND_GLOBAL
  BACKEND_GLOBAL = args[api.PARAM_BACKEND_URL]

  return args[api.PARAM_BACKEND_URL], args


def form_solr_query(args):
  solr_query = ''

  api_key = None
  if api.PARAM_KEY in args:
    api_key = args[api.PARAM_KEY]
    logging.info('api_key = %s' % api_key)

  # args fix up
  if api.PARAM_START not in args:
    args[api.PARAM_START] = 1

  if api.PARAM_SORT not in args:
    args[api.PARAM_SORT] = "score"

  # Generate geo search parameters
  # TODO: formalize these constants
  # this is near the middle of the continental US 
  lat = '37'
  lng = '-95'
  max_dist = 12400
  if args.get(api.PARAM_LAT, None) and args.get(api.PARAM_LNG, None):
    lat = args[api.PARAM_LAT]
    lng = args[api.PARAM_LNG]
    if api.PARAM_VOL_DIST not in args or args[api.PARAM_VOL_DIST] == "":
      args[api.PARAM_VOL_DIST] = DEFAULT_VOL_DIST
    max_dist = args[api.PARAM_VOL_DIST] = int(str(args[api.PARAM_VOL_DIST]))
    if args[api.PARAM_VOL_DIST] < 1:
      args[api.PARAM_VOL_DIST] = DEFAULT_VOL_DIST
    max_dist = float(args[api.PARAM_VOL_DIST])
  
  if args.get(api.PARAM_INVITATIONCODE, ''):
      max_dist = 20030
      
  global GEO_GLOBAL
  geo_params = ('{!geofilt}&pt=%s,%s&sfield=latlong&d=%s&d1=0' 
                   % (str(lat), str(lng), str(max_dist * 1.609))
               )
  geo_params += "&bf=recip(geodist(),1,150,10)"
  GEO_GLOBAL = geo_params

  if (args['is_report'] 
      or (args.get(api.PARAM_TYPE) and args.get(api.PARAM_TYPE, None) != "all")
  ):
    geo_params = ""       
    if args['is_report']:
      GEO_GLOBAL = ''

  # Running our keyword through our categories dictionary to see if we need to adjust our keyword param   
  if api.PARAM_CATEGORY in args:
    for key, val in categories.CATEGORIES.iteritems():
      if str(args[api.PARAM_CATEGORY]) == val:
        args[api.PARAM_CATEGORY] = str(key)   

  # keyword
  original_query = ''
  query_is_empty = False
  if (api.PARAM_Q in args and args[api.PARAM_Q] != ""):
    original_query = args[api.PARAM_Q]
    qwords = args[api.PARAM_Q].split(" ")
    for qi, qw in enumerate(qwords):
      # it is common practice to use a substr of a url eg, volunteermatch 
      # here we transform that to http://*volunteermatch* 
      if qw.find("detailurl:") >= 0 and qw.find("*") < 0:
        ar = qw.split(":")
        if len(ar) > 1:
          ar[1] = "http*" + ar[1] + "*"
          qw = ":".join(ar)
          qwords[qi] = qw
          args[api.PARAM_Q] = ' '.join(qwords)

    # a category in &q means expand to specific terms as opposed to the
    # the solr field 'category' which atm may only be 'vetted'
    args[api.PARAM_Q] = apply_category_query(args[api.PARAM_Q])
    if api.PARAM_CATEGORY in args:        
      args[api.PARAM_Q] += (" AND " + args[api.PARAM_CATEGORY])

    solr_query += rewrite_query('*:* AND ' + args[api.PARAM_Q], api_key)
    ga.track("API", args.get(api.PARAM_KEY, 'UI'), args[api.PARAM_Q])
  elif api.PARAM_CATEGORY in args:
    solr_query += rewrite_query('*:* AND ' + args[api.PARAM_CATEGORY], api_key)
    ga.track("API", args.get(api.PARAM_KEY, 'UI'), args[api.PARAM_CATEGORY])
  else:
    # Query is empty, search for anything at all.
    query_is_empty = True
    solr_query += rewrite_query('*:*', api_key)
    ga.track("API", args.get(api.PARAM_KEY, 'UI'), '*:*')

  # geo params go in first
  global KEYWORD_GLOBAL, STATEWIDE_GLOBAL, NATIONWIDE_GLOBAL
  KEYWORD_GLOBAL = urllib.quote_plus(solr_query)
  STATEWIDE_GLOBAL, NATIONWIDE_GLOBAL = geocode.get_statewide(lat, lng)

  solr_query = urllib.quote_plus(solr_query)
  
  if api.PARAM_TYPE in args and args[api.PARAM_TYPE] != "all":
    # Type: these map to the tabs on the search results page
    # quote plus
    if args[api.PARAM_TYPE] == "self_directed":
      solr_query += urllib.quote_plus(" AND self_directed:true")
    elif args[api.PARAM_TYPE] == "nationwide":
      nationwide_param = args.get('nationwide', '')
      if nationwide_param:
        solr_query += urllib.quote_plus(" AND country:" + nationwide_param)
      solr_query += urllib.quote_plus(" AND micro:false AND self_directed:false")
      
    elif args[api.PARAM_TYPE] == "statewide":
      statewide_param = args.get('statewide', '')
      if statewide_param:
        solr_query += urllib.quote_plus(" AND state:" + statewide_param)
      else:
        solr_query += urllib.quote_plus(" AND (statewide:" + STATEWIDE_GLOBAL + " OR nationwide:" + NATIONWIDE_GLOBAL + ")")
      solr_query += urllib.quote_plus(" AND micro:false AND self_directed:false")

    elif args[api.PARAM_TYPE] == "virtual":
      solr_query += urllib.quote_plus(" AND virtual:true AND micro:false AND self_directed:false")
    elif args[api.PARAM_TYPE] == "micro":
      solr_query += urllib.quote_plus(" AND micro:true")
  else:
    # this keeps the non-geo counts out of the refine by counts
    fq = '&fq='
    fq += urllib.quote('self_directed:false AND virtual:false AND micro:false')
    solr_query += fq
    
  global FULL_QUERY_GLOBAL
  FULL_QUERY_GLOBAL = solr_query
    
  # Source
  global PROVIDER_GLOBAL
  if api.PARAM_SOURCE in args and args[api.PARAM_SOURCE] != "all":    
    PROVIDER_GLOBAL = urllib.quote_plus(" AND provider_proper_name:(" + args[api.PARAM_SOURCE] + ")")
    solr_query += PROVIDER_GLOBAL
  else:
    PROVIDER_GLOBAL = ""  
      
  # for ad campaigns
  if api.PARAM_CAMPAIGN_ID in args:
    # we need to exclude the opted out opportunities
    # they can be tagged as opt_out_all_campaigns
    # or opt_out_campaign_XXX where XXX is the campaign ID.
    exclusion = '!categories:%s !categories:%s' % (
      'optout_all_campaigns',
      'optout_campaign_' + args[api.PARAM_CAMPAIGN_ID]
    )
    # TODO: campaign_ids are per-campaign, but opportunities
    # might prefer to opt out of an entire sponsor.
    # should probably add a 'sponsor_id' to the spreadsheet,
    # and have optout_sponsor_XXX as well.
    solr_query += exclusion

  # set the solr instance we need to use if not given as an arg

  global BACKEND_GLOBAL
  BACKEND_GLOBAL, args = get_solr_backend(args)
  
  solr_query += apply_boosts(args, original_query);
  solr_query += apply_filter_query(api_key, args)

  group_query = ''
  if args.get(api.PARAM_MERGE, None) == '2':
    group_query = ("&group=true&group.field=aggregatefield&group.main=true")
  elif args.get(api.PARAM_MERGE, None) == '3':
    group_query = ("&group=true&group.field=opportunityid&group.main=true")
  elif args.get(api.PARAM_MERGE, None) == '4':
    group_query = ("&group=true&group.field=dateopportunityidgroup&group.main=true&group.limit=7")

  solr_query += group_query

  # add the geo params
  solr_query += '&fq=' + geo_params

  # add the field list
  fields_query = '&fl='
  if api.PARAM_OUTPUT not in args:
    fields_query += ','.join(api.DEFAULT_OUTPUT_FIELDS)
  else:
    if args[api.PARAM_OUTPUT] in api.FIELDS_BY_OUTPUT_TYPE:
      fields_query += ','.join(utils.unique_list(api.DEFAULT_OUTPUT_FIELDS + 
                                               api.FIELDS_BY_OUTPUT_TYPE[args[api.PARAM_OUTPUT]]))
    else:
      fields_query += '*' 

  # TODO: we were getting "URL too long errors"
  fields_query = '&fl=*' 
  solr_query += fields_query

  return solr_query, group_query, fields_query


def parseLatLng(val):
  """ return precisely zero if a lat|lng value is very nearly zero."""
  try:
    if val is None or val == "":
      return 0.0
    floatval = float(val)
    if floatval > -0.01 and floatval < 0.01:
      return 0.0
    return floatval
  except:
    return 0.0

# note: many of the XSS and injection-attack defenses are unnecessary
# given that the callers are also protecting us, but I figure better
# safe than sorry, and defense-in-depth.
def search(args, dumping = False):
  """run a SOLR search."""
  def have_valid_query(args):
    """ make sure we were given a value for at least one of these arguments """
    valid_query = False
    api_list = [api.PARAM_Q,
                api.PARAM_TIMEPERIOD_START,
                api.PARAM_TIMEPERIOD_END,
                api.PARAM_VOL_LOC,
                'virtual',
                api.PARAM_VOL_STARTDATE,
                api.PARAM_VOL_ENDDATE,
                api.PARAM_VOL_DURATION,
                api.PARAM_VOL_PROVIDER,
                api.PARAM_VOL_STARTDAYOFWEEK]

    for param in api_list:
      if param in args and args[param]:
        if param == api.PARAM_VOL_LOC:
          # vol_loc must render a lat, long pair
          if (args[param] != "virtual" and
              not args[api.PARAM_LAT] or 
              parseLatLng(args[api.PARAM_LAT]) == 0 or 
              not args[api.PARAM_LNG] or 
              parseLatLng(args[api.PARAM_LNG]) == 0):
            continue
        valid_query = True
        break
      
    return valid_query

  if api.PARAM_SOLR_PATH in args and args[api.PARAM_SOLR_PATH]:
    args[api.PARAM_BACKEND_URL] = args[api.PARAM_SOLR_PATH]

  if not 'is_report' in args:
    args['is_report'] = False

  solr_query, group_query, fields_query = form_solr_query(args)

  query_url = args[api.PARAM_BACKEND_URL]
  if query_url.find("?") < 0:
    query_url += "?"

  # Return results in JSON format
  # TODO: return in TSV format for fastest possible parsing, i.e. split("\t") 
  query_url += "&wt=json"
  
  # handle &sort= parameter
  if api.PARAM_SORT in args:
    if not args[api.PARAM_SORT] in ['score', 'eventrangend', 'geodist()', 'eventrangestart']:
      query_url += '&sort=' + urllib.quote_plus(args[api.PARAM_SORT])
    else:
      if args[api.PARAM_SORT] == "eventrangeend":
        sortVal = "asc"
      elif args[api.PARAM_SORT] == "geodist()":
        sortVal = "asc"
      elif args[api.PARAM_SORT] == "eventrangestart":
        sortVal = "asc"
      else:
        sortVal = "desc"
      query_url += "&sort=" + args[api.PARAM_SORT] + "%20" + sortVal
    
  # date range
  date_string = ""
  start_datetime_str = None
  if (api.PARAM_VOL_STARTDATE in args and 
      args[api.PARAM_VOL_STARTDATE] != "" and 
      args[api.PARAM_VOL_STARTDATE] != "everything"):

    start_date = datetime.datetime.today()
    try:
      start_date = parse_date(args[api.PARAM_VOL_STARTDATE].strip())      
    except:    
        try:
          start_date = datetime.datetime.strptime(
                         args[api.PARAM_VOL_STARTDATE].strip(), "%m/%d/%Y")      
        except:
          try:
            start_date = datetime.datetime.strptime(
                         args[api.PARAM_VOL_STARTDATE].strip(), "%Y-%m-%d")      
          except:
            logging.info('solr_search.form_solr_query malformed start date: %s' %
                        args[api.PARAM_VOL_STARTDATE])

    end_date = None
    if api.PARAM_VOL_ENDDATE in args and args[api.PARAM_VOL_ENDDATE] != "":
      try:
        end_date = parse_date(args[api.PARAM_VOL_ENDDATE].strip())
      except:
          try:
            end_date = datetime.datetime.strptime(
                           args[api.PARAM_VOL_ENDDATE].strip(), "%m/%d/%Y")
          except:
            try:
              end_date = datetime.datetime.strptime(
                           args[api.PARAM_VOL_ENDDATE].strip(), "%Y-%m-%d")
            except:
              logging.debug('solr_search.form_solr_query malformed end date: %s' %
                           args[api.PARAM_VOL_ENDDATE])
    if not end_date:
      end_date = start_date
    
    try:
      start_datetime_str = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    except:  
        try:
          start_datetime_str = start_date.strftime("%Y-%m-%dT00:00:00.000Z")
        except:
          start_datetime_str = None

    try:
      end_datetime_str = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    except:
        try:
          end_datetime_str = end_date.strftime("%Y-%m-%dT23:59:59.999Z")
        except:
          end_datetime_str = None
      
  global DATE_QUERY_GLOBAL
  if start_datetime_str:
    DATE_QUERY_GLOBAL = ("&fq=(eventrangeend:[" + start_datetime_str + 
                         "+TO+*]+AND+eventrangestart:[*+TO+" + end_datetime_str + "])")
    query_url += DATE_QUERY_GLOBAL
  else:
    DATE_QUERY_GLOBAL = "&fq=(eventrangeend:[NOW-1DAYS%20TO%20*]+OR+expires:[NOW-1DAYS%20TO%20*])"
    query_url += DATE_QUERY_GLOBAL

  if api.PARAM_NUM in args:
    num_to_fetch = int(args[api.PARAM_NUM]) + 1
  else:
    num_to_fetch = 100

  query_url += "&rows=" + str(num_to_fetch)
  query_url += "&start=" + str(int(args[api.PARAM_START]) - 1)

  query_url += "&q=" + solr_query
  if not have_valid_query(args):
    # no query + no location = no results
    result_set = searchresult.SearchResultSet(urllib.unquote(query_url),
                                            query_url,
                                            [])
    logging.debug("SOLR not called: no query given")
    result_set.query_url = query_url
    result_set.args = args
    result_set.num_results = 0
    result_set.estimated_results = 0
    result_set.fetch_time = 0
    result_set.parse_time = 0
    return result_set

  results = query(query_url, group_query, fields_query, args, False, dumping)
  logging.info("SOLR call done: "+str(len(results.results))+
                " results, fetched in "+str(results.fetch_time)+" secs,"+
                " parsed in "+str(results.parse_time)+" secs.")

  # Base doesn't implement day-of-week filtering
  if (api.PARAM_VOL_STARTDAYOFWEEK in args and
      args[api.PARAM_VOL_STARTDAYOFWEEK] != ""):
    startday = args[api.PARAM_VOL_STARTDAYOFWEEK]
    for i, res in enumerate(results):
      dow = str(res.startdate.strftime("%w"))
      if startday.find(dow) < 0:
        del results[i]

  return results


HOC_FACET_FIELDS = [
  'populations_str',
  'skills_str',
  'activitytype_str',
  'country',
  'categorytags_str',
  'eventname_str',
  'impactarea_str',
  'org_name_str',
  'activitytypes_str',
]

HOC_FACET_FIELD_MAP = {
  'org_name' : 'organizationsServed',
  'activitytypes' : 'activityTypes',
}

def apply_HOC_facet_counts(result_set, args):

  node, args = get_solr_backend(args)

  url = node + '?wt=json&q=*:*&rows=0'
  url += '&fq=' + urllib.quote_plus(args.get(api.PARAM_TOCQT, 'feed_providername:handsonnetworkconnect'))

  fetch_result = urlfetch.fetch(url)
  if fetch_result.status_code == 200:
    try:
      json_object = simplejson.loads(fetch_result.content)
      result_set.total_opportunities = int(json_object['response']['numFound'])
    except:
      logging.warning('solr_search.apply_HOC_facet_counts could not get numFound from ' + url)

  url = node + '?wt=json&facet=on&facet.mincount=1&rows=0&indent=on'
  url += DATE_QUERY_GLOBAL 
  url += '&q=' 
  url += FULL_QUERY_GLOBAL 
  url += PROVIDER_GLOBAL 
  url += apply_filter_query(args.get(api.PARAM_KEY, ''), args)
  url += '&facet.field=' + '&facet.field='.join(HOC_FACET_FIELDS)

  fetch_result = urlfetch.fetch(url)
  if fetch_result.status_code == 200:
    json_object = simplejson.loads(fetch_result.content)
    rsp = json_object['facet_counts']['facet_fields']

    for facet_field in HOC_FACET_FIELDS:
      hoc_name = facet_field.replace('_str', '')
      hoc_name = HOC_FACET_FIELD_MAP.get(hoc_name, hoc_name)
      result_set.hoc_facets[hoc_name] = rsp.get(facet_field, [])
    
  return result_set


def get_solr_count(given_query, args):

  rtn = 0

  json_object = None
  node, args = get_solr_backend(args)

  query = given_query.replace(node, '').replace('?&wt=json', '')

  url = node + '?wt=json&rows=0'
  if query.find('group=true') < 0:
    url += query
  else:
    url += '&group.ngroups=true&' + query.replace('&group.main=true', '')

  #print
  #print '<pre>'
  #print url
  #sys.exit(0)

  fetch_result = urlfetch.fetch(url)
  logging.info('solr_search.get_solr_count: ' + url)
  if fetch_result.status_code == 200:
    try:
      json_object = simplejson.loads(fetch_result.content)
    except:
      logging.warning('solr_search.get_solr_count could not get json from ' + url)

  if json_object:
    if not json_object.get('grouped', None):
      try:
        rtn = int(json_object['response']['numFound'])
      except:
        logging.warning('solr_search.get_solr_count could not get numFound from ' + url)
    else:
      group_obj_list = json_object['grouped']
      for gpo in group_obj_list:
        try:
          rtn += int(json_object['grouped'][gpo]['ngroups'])
        except:
          logging.warning('solr_search.get_solr_count could not get group match(es) from ' + url)

  return rtn

# Equirectangular approximation
def calculate_distance(x1, y1, x2, y2):
  """ distance formula applied to lat, long converted to miles """
  return ((((x1 - x2) ** 2) + ((y1 - y2) ** 2)) ** 0.5) * MILES_PER_DEG

# Haversine formula
#def calc_distance(origin, destination):
#    lat1, lon1 = origin
#    lat2, lon2 = destination
def calc_distance(lat1, lon1, lat2, lon2 ):
    #radius = 6371 # km
    radius = 3959 #mi
    dlat = math.radians(lat2-lat1)
    dlon = math.radians(lon2-lon1)
    #a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
    #c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    a = math.sin(dlat/2)** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    d = radius * c
 #   logging.info("distance is :" + str(d) 
 #                + " latLong1: " + str(lat1)
 #                + "," + str(lon1) 
 #                + " , latLong2: " + str(lat2) 
 #                + "," + str(lon2) )
    return d

def query(query_url, group_query, fields_query, args, cache, dumping = False):
  """run the actual SOLR query (no filtering or sorting)."""
  logging.debug("Query URL: " + query_url + '&debugQuery=on')
  result_set = searchresult.SearchResultSet(urllib.unquote(query_url),
                                            query_url, [])

  result_set.query_url = query_url
  result_set.args = args
  result_set.fetch_time = 0
  result_set.parse_time = 0
  
  fetch_start = time.time()
  status_code = 999
  ui_query_url = query_url
  
  api_key = args.get(api.PARAM_KEY, 'UI')
  if api_key == 'UI':
    need_facet_counts = True
  else:
    need_facet_counts = False

  if api_key == 'UI': #For UI searches make two queries one gruoupped by opportunityid to retrieve the VOs IDs and the second to retrieve the dates.
      # The reason is that because of occurrences pagination can not be kept managed solely by rows.
    facetOppsQuery = re.sub('fl=([*,a-z])','fl=opportunityid,feed_providername,event_date_range,title,description,detailurl,latitude,longitude,categorytags&group=true&group.field=opportunityid&group.main=true&group.format=simple',ui_query_url)
    try:
        logging.info("calling SOLR for facetOppsQuery: " + facetOppsQuery)
        facetOppsQuery += '&r=' + str(random.random())
        #fetch_result = urlfetch.fetch(facetOppsQuery, deadline = api.CONST_MAX_FETCH_DEADLINE, headers={"accept-encoding":"gzip"},)
        fetch_result = urlfetch.fetch(facetOppsQuery, deadline = api.CONST_MAX_FETCH_DEADLINE,)
        logging.info("calling SOLR for facetOppsQuery headers: %s " % str(fetch_result.header_msg.getheaders('content-encoding')))
        status_code = fetch_result.status_code
        
        #unzip response if it is compressed
        
        if re.search('gzip', str(fetch_result.header_msg.getheaders('content-encoding'))) and status_code == 200 :
            gzip_stream = StringIO(fetch_result.content)
            gzip_file = gzip.GzipFile(fileobj=gzip_stream)
            result_content = gzip_file.read()
        else:
            result_content = fetch_result.content
        
        result_content = re.sub(r';;', ',', result_content)
        result = simplejson.loads(result_content)
    except:
        # can get a response too large error here
        if status_code == 999:
          logging.warning('solr_search.query error 999 %s' % str(status_code))
        else:
          logging.info('solr_search.query responded %s' % str(status_code))      

    doc_list = result["response"]["docs"]

    #logging.info('facetOppsQuery result' + str(doc_list))
    opportunityList = list() # empty list
    for i, entry in enumerate(doc_list):
        opportunityList.append(entry["opportunityid"])
        #logging.info('opportunityList i=' +  str(i) + ": v=" +str(entry)) 
    opportunityResults = 'opportunityid:(' + '+OR+'.join(opportunityList) + ')'
    logging.info('opportunityList =' +  opportunityResults)
    ui_query_url = re.sub('rows=([0-9]+)','rows=1000',ui_query_url)
    ui_query_url = re.sub('start=([0-9]+)','start=0',ui_query_url)
    ui_query_url = re.sub('fl=([*,a-z])','fl=id,feed_providername,event_date_range,title,description,detailurl,latitude,longitude',ui_query_url)
    ui_query_url = ui_query_url.replace('&q=','&q='+opportunityResults+'+AND+')
     
  try:
    logging.info("calling SOLR: " + ui_query_url)
    ui_query_url += '&r=' + str(random.random())
    fetch_result = urlfetch.fetch(ui_query_url, deadline = api.CONST_MAX_FETCH_DEADLINE, headers={"accept-encoding":"gzip"},)
    #fetch_result = urlfetch.fetch(ui_query_url, deadline = api.CONST_MAX_FETCH_DEADLINE,)
    logging.info("calling SOLR headers: %s " % str(fetch_result.header_msg.getheaders('content-encoding')))
    status_code = fetch_result.status_code
    
    #unzip response if it is compressed
    
    if re.search('gzip', str(fetch_result.header_msg.getheaders('content-encoding'))) and status_code == 200 :      
        gzip_stream = StringIO(fetch_result.content)
        gzip_file = gzip.GzipFile(fileobj=gzip_stream)
        result_content = gzip_file.read()
    else:
        result_content = fetch_result.content
    
    result_content = re.sub(r';;', ',', result_content)
    result = simplejson.loads(result_content)
  except:
    # can get a response too large error here
    if status_code == 999:
      logging.warning('solr_search.query error')
    else:
      logging.info('solr_search.query responded %s' % str(status_code))

  fetch_end = time.time()
  result_set.fetch_time = fetch_end - fetch_start
  if status_code != 200:
    return result_set
  #result_content = fetch_result.content

  parse_start = time.time()
  # undo comma encoding -- see datahub/footprint_lib.py
  # result_content = re.sub(r';;', ',', result_content)
  # result = simplejson.loads(result_content)
  
  all_facets = None
  if need_facet_counts:
    all_facets = get_geo_counts(args, api_key)

  if not all_facets or not "facet_counts" in all_facets:    
      result_set.facet_counts = None
  else:
    facet_counts = dict()    
    ks = "self_directed:false AND virtual:false AND micro:false"
    if not args['is_report'] and not args.get(api.PARAM_INVITATIONCODE, None):
      ks += " AND -statewide:[* TO *] AND -nationwide:[* TO *]"
    facet_counts["all"] = int(all_facets["facet_counts"]["facet_queries"][ks])

    facet_counts.update(get_type_counts(args, api_key))    
    count = 0;
    if api.PARAM_TYPE in args:
      if args[api.PARAM_TYPE] == "statewide":
        count = facet_counts["statewide"]
      elif args[api.PARAM_TYPE] == "virtual":
        count = facet_counts["virtual"]
      elif args[api.PARAM_TYPE] == "self_directed":
        count = facet_counts["self_directed"]
      elif args[api.PARAM_TYPE] == "micro":
        count = facet_counts["micro"]
      else:
        count = facet_counts["all"]

    facet_counts["count"] = count
    result_set.facet_counts = facet_counts
    facets = get_facet_counts(api_key, args)
    result_set.categories = facets['category_fields']
    result_set.providers = facets['provider_fields']
    
  doc_list = result["response"]["docs"]
  
  #process json doc list
  for i, entry in enumerate(doc_list):
    if not "detailurl" in entry:
      # URL is required 
      latstr = entry["latitude"]
      longstr = entry["longitude"]
      if latstr and longstr and latstr != "" and longstr != "":
        entry["detailurl"] = "http://maps.google.com/maps?q=" + str(latstr) + "," + str(longstr)
      else:
        logging.info('solr_search.query skipping SOLR record' +
                      ' %d: detailurl is missing...' % i)
        continue

    url = entry["detailurl"]
    # ID is the 'stable id' of the item generated by base.
    # Note that this is not the base url expressed as the Atom id element.
    item_id = entry["id"]
    # Base URL is the url of the item in base. For Solr we just use the ID hash
    base_url = item_id
    snippet = entry.get('description', '')
    title = entry.get('title', '')
    location = entry.get('location_string', '')

    categories = entry.get('categories', '')
    if type(categories).__name__ != 'list':
      try:
        categories = categories.split(',')
      except:
        categories = []

    vetted = False
    if 'Vetted' in categories:
      vetted = True

    is_501c3 = False
    if entry.get('is_501c3', ''):
      is_501c3 = True

    org_name = entry.get('org_name', '')
    if re.search(r'[^a-z]acorn[^a-z]', " "+org_name+" ", re.IGNORECASE):
      logging.debug('solr_search.query skipping: ACORN in org_name')
      continue

    latstr = entry["latitude"]
    longstr = entry["longitude"]
    virtual = entry.get('virtual')
    self_directed = entry.get("self_directed")
    micro = entry.get("micro")
    volunteers_needed = entry.get("volunteersneeded")

    res = searchresult.SearchResult(url, title, snippet, location, item_id,
                                    base_url, volunteers_needed, virtual,
                                    self_directed, micro, categories, org_name, 
                                    vetted, is_501c3)

    # TODO: escape?
    res.provider = entry["feed_providername"]
    if (res.provider == "myproj_servegov" and
        re.search(r'[^a-z]acorn[^a-z]', " "+result_content+" ", re.IGNORECASE)):
      # per-provider rule because case-insensitivity
      logging.info('solr_search.query skipping: ACORN in for myproj_servegov')
      continue

    res.orig_idx = i+1

    res.latlong = ""
    res.distance = ''
    res.duration = ''
    if latstr and longstr:
      res.latlong = str(latstr) + "," + str(longstr)
      try:
        res.distance = str(calc_distance(float(args[api.PARAM_LAT])
                                              , float(args[api.PARAM_LNG])
                                              , float(latstr)
                                              , float(longstr)))
      except:
        pass

    # res.event_date_range follows one of these two formats:
    #     <start_date>T<start_time> <end_date>T<end_time>
    #     <date>T<time>
    res.event_date_range = entry["event_date_range"]
    res.startdate = datetime.datetime.strptime("2000-01-01", "%Y-%m-%d")
    res.enddate = datetime.datetime.strptime("2038-01-01", "%Y-%m-%d")
    if not dumping and res.event_date_range:
      match = DATE_FORMAT_PATTERN.findall(res.event_date_range)
      if not match:
        logging.debug('solr_search.query skipping record' +
                        ' %d: bad date range: %s for %s' % 
                        (i, res.event_date_range, url))
        continue
      else:
        # first match is start date/time
        startdate = datetime.datetime.strptime(match[0], '%Y-%m-%dT%H:%M:%S')
        # last match is either end date/time or start/date time
        enddate = datetime.datetime.strptime(match[-1], '%Y-%m-%dT%H:%M:%S')
        # protect against absurd dates
        if startdate > res.startdate:
          res.startdate = startdate
        if enddate < res.enddate:
          res.enddate = enddate

        if res.startdate and res.enddate:
          delta = res.enddate - res.startdate
          res.duration = str(delta.days)

    for name in utils.unique_list(apiwriter.STANDARD_FIELDS + apiwriter.EXELIS_FIELDS + apiwriter.HOC_FIELDS + apiwriter.CALENDAR_FIELDS):
      name = name.lower()
      if len(name) >= 2 and not hasattr(res, name) or not getattr(res, name, None):
        value = entry.get(name, '')
        if not isinstance(value, list):
          setattr(res, name, str(value))
        else:
          setattr(res, name, '\t'.join(value))
    
    # posting.py currently has an authoritative list of fields in "argnames"
    # that are available to submitted events which may later appear in GBase
    # so with a few exceptions we want those same fields to become
    # attributes of our result object
    except_names = ["title", "description"]
    for name in posting.argnames:
      if name not in except_names and name.lower() in entry:
        # Solr field names are all lowercase.
        # TODO: fix list in posting.py so it matches solr's fieldnames.
        setattr(res, name, entry[name.lower()])

    result_set.results.append(res)
    if cache and res.item_id:
      key = RESULT_CACHE_KEY + res.item_id
      memcache.set(key, res, time=RESULT_CACHE_TIME)

  result_set.num_results = len(result_set.results)
  result_set.total_match = int(result["response"]["numFound"])
  result_set.merged_count = result_set.backend_count = result_set.estimated_results = result_set.total_match

  if group_query:
    cq = query_url.replace(fields_query, '').replace(group_query, '')
    result_set.backend_count = get_solr_count(cq, args)
    cq = query_url.replace(fields_query, '')
    result_set.merged_count = get_solr_count(cq, args)

  parse_end = time.time()
  result_set.parse_time = parse_end - parse_start

  return result_set


def get_facet_counts(api_key, args):
  """ get the category/provider counts to be displayed in refine by section """

  category_fields = dict()
  provider_fields = []
  query = []

  for key, val in categories.CATEGORIES.iteritems():
    query.append("facet.query=" + urllib.quote_plus(key))  

  query_url = (BACKEND_GLOBAL + '?wt=json' + DATE_QUERY_GLOBAL 
            + '&q=' + FULL_QUERY_GLOBAL + PROVIDER_GLOBAL + '&fq=' + GEO_GLOBAL
            + '&facet.mincount=1&facet.field=provider_proper_name_str&facet=on&rows=0&' + "&".join(query))

  query_url += apply_filter_query(api_key, args)

  logging.info("get_facet_counts: " + query_url)

  try:
    fetch_result = urlfetch.fetch(query_url, deadline = api.CONST_MAX_FETCH_DEADLINE)
  except:
    logging.error('get_facet_counts: error receiving solr facet counts')
    sys.exit(0)

  result_content = fetch_result.content
  result_content = re.sub(r';;', ',', result_content)
  json = simplejson.loads(result_content)["facet_counts"]

  queries = json["facet_queries"]
  providers = json["facet_fields"]["provider_proper_name_str"]
    
  for k, v in queries.iteritems():
    if v > 0:
      category_fields[categories.CATEGORIES[k]] = v
    
  for k, v in enumerate(providers):
    if int(k) % 2 == 1:
      continue;
    else:
      provider_fields.append({str(v) : str(providers[k + 1])})
    
  return {'category_fields': sorted(category_fields.iteritems(), 
          key=itemgetter(1), reverse=True), 'provider_fields': provider_fields}    


def get_geo_counts(args, api_key):
  """ get counts to be displayed in the tabs across top """

  query_url = (BACKEND_GLOBAL + '?wt=json' + DATE_QUERY_GLOBAL 
               + '&fq=' + GEO_GLOBAL + '&q=' + KEYWORD_GLOBAL + PROVIDER_GLOBAL 
               + '&facet=on&facet.mincount=1&rows=0'
               + '&facet.query=self_directed:false+AND+virtual:false+AND+micro:false'
              )
    
  if not args['is_report'] and not args.get(api.PARAM_INVITATIONCODE, None):
    query_url += urllib.quote_plus(' AND -statewide:[* TO *] AND -nationwide:[* TO *]')

  query_url += apply_filter_query(api_key, args)
  logging.info("get_geo_counts: " + query_url)

  try:
    fetch_result = urlfetch.fetch(query_url, deadline = api.CONST_MAX_FETCH_DEADLINE)
  except:
    logging.error('get_geo_counts: error receiving solr facet counts')
    sys.exit(0)
  
  try:
    result_content = fetch_result.content  
  except:
    result_content = ''

  # undo comma encoding -- see datahub/footprint_lib.py
  result_content = re.sub(r';;', ',', result_content)
  return simplejson.loads(result_content)


def get_type_counts(args, api_key):
  """ tabs: my area, statewide, virtual, micro """

  query_url = (BACKEND_GLOBAL + '?wt=json' 
               + DATE_QUERY_GLOBAL + '&q=' + KEYWORD_GLOBAL + PROVIDER_GLOBAL 
               + '&facet=on&facet.limit=100' 
               + '&facet.field=virtual&facet.field=self_directed&facet.field=micro&rows=0'
               + '&facet.field=statewide&facet.field=nationwide'
              )

  query_url += apply_filter_query(api_key, args)
  logging.info("get_type_counts: " + query_url)

  try:
    fetch_result = urlfetch.fetch(query_url, deadline = api.CONST_MAX_FETCH_DEADLINE)
  except:
    logging.error('get_type_counts: error receiving solr facet counts')
    sys.exit(0)
  
  result_content = fetch_result.content  
  # undo comma encoding -- see datahub/footprint_lib.py
  result_content = re.sub(r';;', ',', result_content)
  result = simplejson.loads(result_content)
  if "facet_counts" in result:
    facet_fields = result["facet_counts"]["facet_fields"]
    facet_counts = dict()
    for k, v in facet_fields.iteritems():
      if k == "nationwide" and NATIONWIDE_GLOBAL:
        facet_counts[k] = 0
        for idx, st in enumerate(facet_fields["nationwide"]):
          if st == NATIONWIDE_GLOBAL:
            try:
              facet_counts[k] = facet_fields["nationwide"][idx + 1]
            except:
              pass
            break
      elif k == "statewide" and STATEWIDE_GLOBAL:
        facet_counts[k] = 0
        for idx, st in enumerate(facet_fields["statewide"]):
          if st == STATEWIDE_GLOBAL:
            try:
              facet_counts[k] = facet_fields["statewide"][idx + 1]
            except:
              pass
            break
      else:
        if "true" in v:
          index = v.index("true")
        else:
          index = -1        
        if index >= 0:
          facet_counts[k] = v[index + 1]
        else:
          facet_counts[k] = 0

    if 'statewide' in facet_counts and 'nationwide' in facet_counts:
      facet_counts['statewide'] += facet_counts['nationwide']

    # remove micro counts because they were incorrectly tagged as virtual
    facet_counts["virtual"] -= facet_counts["micro"] 
    # remove self_directed counts because they were incorrectly tagged as virtual
    facet_counts["virtual"] -= facet_counts["self_directed"] 

  return facet_counts

