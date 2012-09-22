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
core classes for testing the API.
"""

from google.appengine.api import urlfetch
from google.appengine.api import memcache
from xml.dom import minidom
import xml.sax.saxutils
import re
import hashlib
import random
import math
import logging
from urlparse import urlsplit
from google.appengine.ext import db
from urllib import urlencode

from fastpageviews.pagecount import TEST_API_KEY

DEFAULT_TEST_URL = 'http://footprint2009dev.appspot.com/api/volopps'
DEFAULT_RESPONSE_TYPES = 'rss'
LOCAL_STATIC_URL = 'http://localhost:8080/test/sampleData.xml'
CURRENT_STATIC_XML = 'sampleData0.1.xml'

#'query, num, start, provider'
"""
when we paginate, the overfetch causes lower-ranking Base results to
   be considered for top slots, and sometimes they win them because we
   use a very different ranking/ordering algorithm.  This also means that
   changing &num= can change ranking/ordering as well, and worse, as
   we paginate through results, we might actually see the same results
   again (rarely).

disabling the &start test for now
"""
#ALL_TEST_TYPES = 'num, query, provider, start, geo, snippets'
ALL_TEST_TYPES = 'num, query, provider, geo, snippets'

class TestResultCode(db.IntegerProperty):
  """success and failure types."""
  # pylint: disable-msg=W0232
  # pylint: disable-msg=R0903
  PASS = 0
  UNKNOWN_FAIL = 1
  INTERNAL_ERROR = 2
  LOW_LEVEL_PARSE_FAIL = 3
  DATA_MISMATCH = 4

class TestResults(db.Model):
  """results of running tests."""
  # pylint: disable-msg=W0232
  # pylint: disable-msg=R0903
  timestamp = db.DateTimeProperty(auto_now=True)
  test_type = db.StringProperty()
  result_code = TestResultCode()
  result_string = db.StringProperty()

class ApiResult(object):
  """result object used for testing."""
  # pylint: disable-msg=R0903
  def __init__(self, item_id, title, description, url, provider, latlong):
    self.item_id = item_id
    self.title = title
    self.description = description
    self.url = url
    self.provider = provider
    self.latlong = latlong

def get_node_data(entity):
  """returns the value of a DOM node with some escaping, substituting
  "" (empty string) if no child/value is found."""
  if entity.firstChild == None:
    return ""
  if entity.firstChild.data == None:
    return ""
  nodestr = entity.firstChild.data
  nodestr = xml.sax.saxutils.escape(nodestr).encode('UTF-8')
  nodestr = re.sub(r'\n', r'\\n', nodestr)
  return nodestr
    
def get_children_by_tagname(elem, name):
  """returns a list of children nodes whose name matches."""
  # TODO: use list comprehension?
  temp = []
  for child in elem.childNodes:
    if child.nodeType == child.ELEMENT_NODE and child.nodeName == name:
      temp.append(child)
  return temp
  
def get_tag_value(entity, tag):
  """within entity, find th first child with the given tagname, then
  return its value, processed to UTF-8 and with newlines escaped."""
  #print "----------------------------------------"
  nodes = entity.getElementsByTagName(tag)
  #print "nodes: "
  #print nodes
  if nodes.length == 0:
    return ""
  #print nodes[0]
  if nodes[0] == None:
    return ""
  if nodes[0].firstChild == None:
    return ""
  if nodes[0].firstChild.data == None:
    return ""
  #print nodes[0].firstChild.data
  outstr = nodes[0].firstChild.data
  outstr = xml.sax.saxutils.escape(outstr).encode('UTF-8')
  outstr = re.sub(r'\n', r'\\n', outstr)
  return outstr

def parse_rss(data):
  """convert an RSS response to an ApiResult."""
  result = []
  xmldoc = minidom.parseString(data)
  items = xmldoc.getElementsByTagName('item')
  for item in items:
    api_result = (ApiResult(
        get_tag_value(item, 'fp:id'),
        get_tag_value(item, 'title'),
        get_tag_value(item, 'description'), 
        get_tag_value(item, 'link'),
        get_tag_value(item, 'fp:provider'),
        get_tag_value(item, 'fp:latlong')))
    result.append(api_result)
  return result

def random_item(items):
  """pick a random item from a list.  TODO: is there a more concise
  way to do this in python?"""
  num_items = len(items)
  if num_items == 1:
    return items[0]
  else:
    return items[random.randrange(0, num_items - 1)]
    
def retrieve_raw_data(full_uri):
  """call urlfetch and cache the results in memcache."""
  print full_uri
  memcache_key = hashlib.md5('api_test_data:' + full_uri).hexdigest()
  result_content = memcache.get(memcache_key)
  if not result_content:
    fetch_result = urlfetch.fetch(full_uri)
    if fetch_result.status_code != 200:
      return None
    result_content = fetch_result.content
    # memcache.set(memcache_key, result_content, time=300)
  return result_content
  
def in_location(opp, loc, radius):
  """is given opportunity within the radius of loc?"""
  loc_arr = loc.split(',')
  opp_arr = opp.latlong.split(',')
  
  loc_lat = math.radians(float(loc_arr[0].strip()))
  loc_lng = math.radians(float(loc_arr[1].strip()))
  opp_lat = math.radians(float(opp_arr[0].strip()))
  opp_lng = math.radians(float(opp_arr[1].strip()))
  
  dlng = opp_lng - loc_lng
  dlat = opp_lat - loc_lat #lat_2 - lat_1
  # TODO: rename a_val and c_val to human-readable (named for pylint)
  a_val = (math.sin(dlat / 2))**2 + \
          (math.sin(dlng / 2))**2 * math.cos(loc_lat) * math.cos(opp_lat)
  c_val = 2 * math.asin(min(1, math.sqrt(a_val)))
  dist = 3956 * c_val
  return (dist <= radius)
  
class ApiTesting(object):
  """class to hold testing methods."""
  # pylint: disable-msg=R0904
  def __init__(self, wsfi_app):
    self.web_app = wsfi_app
    self.num_failures = 0
    self.api_url = None
    self.response_type = None
    self.test_type = ""
    
  def success(self, datastore_insert):
    """note a test success."""
    self.datastore_insert = datastore_insert

    # test whether to insert entity into the Datastore
    if self.datastore_insert:
      # report test success. returns True to make it easy on callers.
      res = TestResults(test_type=self.test_type,
                        result_code=TestResultCode.PASS)
      res.put()
    self.output('<p class="result success">Passed</p>')
    return True

  def fail(self, code, msg, datastore_insert):
    """note a test failure."""
    self.datastore_insert = datastore_insert
    # test whether to insert entity into the Datastore
    if self.datastore_insert:
      # report test failure. returns False to make it easy on callers.
      res = TestResults(test_type=self.test_type, result_code=code,
                        result_string=msg)
      res.put()
    self.num_failures += 1
    self.output('<p class="result fail">Fail. <span>'+msg+'</span></p>')
    # stick something in the logs, so it shows up in the appengine dashboard 
    logging.error('testapi fail: '+msg)
    return False

  def print_details(self, msg):
    """print extra error details for humans, which aren't logged.
    returns False for convenience of callers."""
    self.output('<p class="result amplification">'+msg+'</p>')
    return False
    
  def output(self, html):
    """macro: output some HTML."""
    self.web_app.response.out.write(html)
    
  def make_uri(self, options):
    """generate an API call given args."""
    result = self.api_url + '?output=' + self.response_type + '&'
    result += 'key=%s&' % TEST_API_KEY
    result += urlencode(options)
    logging.debug('testapi.helpers.make_uri = %s' % result)
    return result
  
  def assert_nonempty_results(self, result_set):
    """require that the results are valid (returns true/false).
    Handles the fail() call internally, but not the success() call."""
    if result_set is None or result_set == False or len(result_set) == 0:
      return self.fail(
        TestResultCode.DATA_MISMATCH,
        "test_"+self.test_type+": expected non-empty results.", True)
    return True
  
  def assert_empty_results(self, result_set):
    """require that the results are valid (returns true/false).
    Handles the fail() call internally, but not the success() call."""
    if result_set is None:
      return self.fail(
        TestResultCode.INTERNAL_ERROR,
        "test_"+self.test_type+": result_set invalid.", True)
    if len(result_set) == 0:
      return True
    return self.fail(
      TestResultCode.DATA_MISMATCH,
      "test_"+self.test_type+": expected empty results.", True)
  
  def parse_raw_data(self, data):
    """wrapper for parse_TYPE()."""
    if self.response_type == 'rss':
      return parse_rss(data)
    elif self.response_type == 'xml':
      # TODO: implement: return self.parse_xml(data)
      return []
    return []
  
  def run_test(self, test_type):
    """run one test."""
    self.test_type = test_type.strip()
    msg = 'test_type='+self.test_type
    if self.response_type != "rss":
      msg += '&amp;output=' + self.response_type
    self.output('<p class="test">Running <em>'+msg+'</em></p>')
    test_func = getattr(self, 'test_' + self.test_type, None)
    if callable(test_func):
      return test_func()
    return self.fail(
      TestResultCode.INTERNAL_ERROR,
      'No such test <strong>'+self.test_type+'</strong> in suite.', True)

  def datastore_test_check(self, testresult, test_type):
    """read the TestResult object and report success or failure"""
    self.test_type = test_type
    self.testresult = testresult
    msg = 'test_type=' +self.test_type
    datemsg = 'Date of last run: ' +str(self.testresult.timestamp)
    if self.response_type != "rss":
      msg += '&amp;output=' + self.response_type
    self.output('<p class="test">Checking Datastore for <em>'+msg+'</em></p>'+
                datemsg)
    if self.testresult.result_code == 0:
      return self.success(False)
    elif self.testresult.result_code == 4:
      return self.fail(
        TestResultCode.DATA_MISMATCH,
        self.testresult.result_string, False)
    elif self.testresult.result_code == 3:
      return self.fail(
        TestResultCode.LOW_LEVEL_PARSE_FAIL,
        self.testresult.result_string, False)
    elif self.testresult.result_code == 2:
      return self.fail(
        TestResultCode.INTERNAL_ERROR,
        self.testresult.result_string, False)
    else:
      return self.fail(
        TestResultCode.UNKNOWN_FAIL,
        self.testresult.result_string, False)
  
  def run_tests(self, test_type, api_url, response_type, read_from_cache):
    """run multiple tests (comma-separated).  beware of app engine timeouts!"""
    self.api_url = api_url
    self.response_type = response_type
    self.read_from_cache = read_from_cache
    if test_type == 'all':
      test_type = ALL_TEST_TYPES
    test_types = test_type.split(',')
    res = True

    for test_type in test_types:
      test_type = test_type.strip()
      if self.read_from_cache:
        # query the Datastore for existing test data
        testresults = db.GqlQuery("SELECT * FROM TestResults " +
                                  "WHERE test_type = :1 " +
                                  #"AND result_code = 0 " +
                                  "ORDER BY timestamp DESC", test_type)
        testresult = testresults.get()

        if testresult:
          res = self.datastore_test_check(testresult, test_type)
        else:
          if not self.run_test(test_type):
            res = False
      else:
        if not self.run_test(test_type):
          res = False
    return res
  
  def get_result_set(self, arg_list):
    """macro for forming and making a request and parsing the results."""
    full_uri = self.make_uri(arg_list)
    self.output('<p class="uri">Fetching result set for following tests</p>')
    self.output('<p class="uri">URI: ' + full_uri + '</p>')
    
    try:
      data = retrieve_raw_data(full_uri)
      return self.parse_raw_data(data)
    except:
      self.fail(TestResultCode.LOW_LEVEL_PARSE_FAIL,
                'parse_raw_data: unable to parse response.', True)
    return None
  
  def test_num(self):
    """test whether the result set has a given number of results."""
    expected_count = int(random_item(['7', '14', '21', '28', '57']))
    result_set = self.get_result_set({'q':'in', 'num':expected_count})
    if not self.assert_nonempty_results(result_set):
      return False
    if len(result_set) != expected_count:
      return self.fail(TestResultCode.DATA_MISMATCH,
                       'Requested num='+str(expected_count)+' but received '+
                       str(len(result_set))+' results.', True)
    return self.success(True)
  
  def int_test_bogus_query(self):
    """ try a few bogus locations to make sure there's no weird data """
    term = random_item(["fqzzqx"])
   
    result_set = self.get_result_set({'q':term})
    if self.assert_empty_results(result_set):
      return self.success(True)
    else:
      return self.fail(
        TestResultCode.DATA_MISMATCH,
        'some item(s) found for search term <strong>' + term +
        '</strong> or result set invalid', True)
   
  def int_test_valid_query(self):
    """run a hardcoded test query (q=)."""
    result = True
    term = random_item(["hospital", "walk", "help", "read", "children",
                        "mercy"])
  
    result_set = self.get_result_set({'q':term})
    if not self.assert_nonempty_results(result_set):
      return False

    result = True
    for opp in result_set:
      if (not re.search(term, opp.title, re.I) and
          not re.search(term, opp.description, re.I)):
        self.print_details('Did not find search term <strong>'+term+
                           '</strong> in item '+opp.title+': '+opp.description)
        result = False
    if not result:
      return self.fail(
        TestResultCode.DATA_MISMATCH,
        'some item(s) did not match search term <strong>' + term, True)
    return self.success(True)
    
  def test_query(self):
    """run a set of query term tests."""
    self.int_test_valid_query()
    self.int_test_bogus_query()
  
  def int_test_bogus_geo(self):
    """ try a few bogus locations to make sure there's no weird data """
    location = random_item(["fqzvzqx"])
  
    result_set = self.get_result_set({'vol_loc':location})
    if self.assert_empty_results(result_set):
      return self.success(True)
    else:
      return self.fail(TestResultCode.DATA_MISMATCH,
                       'some item(s) found for location <strong>' + location +
                       '</strong> or result set invalid', True)
   
  def int_test_valid_geo(self):
    """run a query and check the geo results."""
    loc = random_item(["37.8524741,-122.273895", "33.41502,-111.82298",
                       "33.76145285137889,-84.38941955566406",
                       "29.759956,-95.362534"])
    radius = random_item(["10", "20", "30", "50"])
    result_set = self.get_result_set({'vol_loc':loc, 'vol_dist':radius,
                                      'num':20})
    if not self.assert_nonempty_results(result_set):
      return False

    result = True
    for opp in result_set:
      if not in_location(opp, loc, radius):
        self.print_details('Item outside location/distance <strong>'+opp.id+
                           ': '+opp.title+'</strong> '+opp.latlong)
        result = False
    if not result:
      return self.fail(
        TestResultCode.DATA_MISMATCH,
        'One or more items did not fall in the requested location/distance.',
        True)
    return self.success(True)
  
  def test_geo(self):
    """run a set of geo tests."""
    self.int_test_valid_geo()
    self.int_test_bogus_geo()
    
  def test_provider(self):
    """run a hardcoded test query (&vol_provider=)."""
    provider = "unitedway"
    result_set = self.get_result_set({'q':'hospital', 'vol_provider':provider})
    if not self.assert_nonempty_results(result_set):
      return False

    result = True
    for opp in result_set:
      if re.search(provider, opp.provider, re.I) == None:
        self.print_details('Wrong provider <strong>'+opp.provider+'</strong>'+
                           'found in item <em>'+opp.title+'</em>')
        result = False
    if not result:
      return self.fail(
        TestResultCode.DATA_MISMATCH,
        'One or more items did not match provider <strong>provider+</strong>',
        True)
    return self.success(True)
  
  def test_start(self):
    """
      Tests two result sets to ensure that the API 'start' parameter is
      valid. Assumes:
        result_set1 and result_set2 must overlap (i.e. (start2 - start1) < num_items)
        start1 < start2
        
      Simply tests to make sure that result_set1[start2] = result_set2[start1]
      and continues testing through the end of the items that should overlap
    """
    start1 = 1
    start2 = 5
    num_items = 10
    result_set1 = self.get_result_set({'q':'in', 
        'num': num_items, 'start': start1})
    result_set2 = self.get_result_set({'q':'in', 
        'num': num_items, 'start': start2})
    if (not self.assert_nonempty_results(result_set1) or
        not self.assert_nonempty_results(result_set2)):
      return False

    result = True
    for i in range(start2, num_items):
      opp1 = result_set1[i]
      opp2 = result_set2[start1 + (i - start2)]
      if opp1.title != opp2.title:
        self.print_details('List items different, <em>'+opp1.title+'</em> != '+
                           '<em>'+opp2.title+'</em>')
        result = False
    if not result:
      return self.fail(
        TestResultCode.DATA_MISMATCH,
        'Start param returned non-overlapping results.', True)
    return self.success(True)

  def test_snippets(self):
    """ensure that /ui_snippets returns something valid."""
    pieces = urlsplit(self.api_url)
    domain = pieces.netloc
    self.print_details(domain)
    data = retrieve_raw_data('http://'+domain+'/ui_snippets?q=a&cache=0')
    if not data:
      return self.fail(
        TestResultCode.UNKNOWN_FAIL,
        'misc problem with /ui_snippets', True)
    return self.success(True)

