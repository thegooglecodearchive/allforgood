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

# TODO: remove silly dependency on dapper.net-- thought I'd need
# it for the full scrape, but ended up not going that way.

"""open source load testing tool for footprint."""

import sys
import os
import urllib
import urlparse
import re
import thread
import time
from datetime import datetime
import socket
import random
import cookielib
import getpass
import logging
import hashlib
import mimetypes
import optparse
import os
import re
import socket
import subprocess
import sys
import urllib
import urllib2
import urlparse
import tempfile
try:
  import readline
except ImportError:
  logging.debug("readline not found.")
  pass

# match appengine's timeout
DEFAULT_TIMEOUT = 30
socket.setdefaulttimeout(DEFAULT_TIMEOUT)

# to identify pages vs. hits, we prefix page with a given name
PAGE_NAME_PREFIX = "page_"

# The logging verbosity:
#  0: Errors only.
#  1: Status messages.
#  2: Info logs.
#  3: Debug logs.
VERBOSITY = 1

def AreYouSureOrExit(exit_if_no=True):
  prompt = "Are you sure you want to continue?(y/N) "
  answer = raw_input(prompt).strip()
  if exit_if_no and answer.lower() != "y":
    ErrorExit("User aborted")
  return answer.lower() == "y"

def GetEmail(prompt):
  """Prompts the user for their email address and returns it.

  The last used email address is saved to a file and offered up as a suggestion
  to the user. If the user presses enter without typing in anything the last
  used email address is used. If the user enters a new address, it is saved
  for next time we prompt.

  """
  last_email_file_name = os.path.expanduser("~/.last_loadtest_email_address")
  last_email = ""
  if os.path.exists(last_email_file_name):
    try:
      last_email_file = open(last_email_file_name, "r")
      last_email = last_email_file.readline().strip("\n")
      last_email_file.close()
      prompt += " [%s]" % last_email
    except IOError, e:
      pass
  email = raw_input(prompt + ": ").strip()
  if email:
    try:
      last_email_file = open(last_email_file_name, "w")
      last_email_file.write(email)
      last_email_file.close()
    except IOError, e:
      pass
  else:
    email = last_email

  if email.find("@") == -1:
    email += "@gmail.com"
    print "assuming you mean "+email+"@gmail.com"

  return email


def StatusUpdate(msg):
  """Print a status message to stdout.

  If 'VERBOSITY' is greater than 0, print the message.

  Args:
    msg: The string to print.
  """
  if VERBOSITY > 0:
    print msg


def ErrorExit(msg):
  """Print an error message to stderr and exit."""
  print >>sys.stderr, msg
  sys.exit(1)


class ClientLoginError(urllib2.HTTPError):
  """Raised to indicate there was an error authenticating with ClientLogin."""

  def __init__(self, url, code, msg, headers, args):
    urllib2.HTTPError.__init__(self, url, code, msg, headers, None)
    self.args = args
    self.reason = args["Error"]


class AbstractRpcServer(object):
  """Provides a common interface for a simple RPC server."""

  def __init__(self, host, auth_function, host_override=None, extra_headers={},
               save_cookies=False):
    """Creates a new HttpRpcServer.

    Args:
      host: The host to send requests to.
      auth_function: A function that takes no arguments and returns an
        (email, password) tuple when called. Will be called if authentication
        is required.
      host_override: The host header to send to the server (defaults to host).
      extra_headers: A dict of extra headers to append to every request.
      save_cookies: If True, save the authentication cookies to local disk.
        If False, use an in-memory cookiejar instead.  Subclasses must
        implement this functionality.  Defaults to False.
    """
    self.host = host
    self.host_override = host_override
    self.auth_function = auth_function
    self.authenticated = False
    self.extra_headers = extra_headers
    self.save_cookies = save_cookies
    self.opener = self._GetOpener()
    if self.host_override:
      logging.info("Server: %s; Host: %s", self.host, self.host_override)
    else:
      logging.info("Server: %s", self.host)

  def _GetOpener(self):
    """Returns an OpenerDirector for making HTTP requests.

    Returns:
      A urllib2.OpenerDirector object.
    """
    raise NotImplementedError()

  def _CreateRequest(self, url, data=None):
    """Creates a new urllib request."""
    logging.debug("Creating request for: '%s' with payload:\n%s", url, data)
    req = urllib2.Request(url, data=data)
    if self.host_override:
      req.add_header("Host", self.host_override)
    for key, value in self.extra_headers.iteritems():
      req.add_header(key, value)
    return req

  def _GetAuthToken(self, email, password):
    """Uses ClientLogin to authenticate the user, returning an auth token.

    Args:
      email:    The user's email address
      password: The user's password

    Raises:
      ClientLoginError: If there was an error authenticating with ClientLogin.
      HTTPError: If there was some other form of HTTP error.

    Returns:
      The authentication token returned by ClientLogin.
    """
    account_type = "GOOGLE"
    if self.host.endswith(".google.com"):
      # Needed for use inside Google.
      account_type = "HOSTED"
    account_type = "GOOGLE"
    req = self._CreateRequest(
        url="https://www.google.com/accounts/ClientLogin",
        data=urllib.urlencode({
            "Email": email,
            "Passwd": password,
            "service": "ah",
            "source": "rietveld-codereview-upload",
            "accountType": account_type,
        }),
    )
    try:
      response = self.opener.open(req)
      response_body = response.read()
      response_dict = dict(x.split("=")
                           for x in response_body.split("\n") if x)
      return response_dict["Auth"]
    except urllib2.HTTPError, e:
      if e.code == 403:
        body = e.read()
        response_dict = dict(x.split("=", 1) for x in body.split("\n") if x)
        raise ClientLoginError(req.get_full_url(), e.code, e.msg,
                               e.headers, response_dict)
      else:
        raise

  def _GetAuthCookie(self, auth_token):
    """Fetches authentication cookies for an authentication token.

    Args:
      auth_token: The authentication token returned by ClientLogin.

    Raises:
      HTTPError: If there was an error fetching the authentication cookies.
    """
    # This is a dummy value to allow us to identify when we're successful.
    continue_location = "http://localhost/"
    args = {"continue": continue_location, "auth": auth_token}
    req = self._CreateRequest("http://%s/_ah/login?%s" %
                              (self.host, urllib.urlencode(args)))
    try:
      response = self.opener.open(req)
    except urllib2.HTTPError, e:
      response = e
    if (response.code != 302 or
        response.info()["location"] != continue_location):
      raise urllib2.HTTPError(req.get_full_url(), response.code, response.msg,
                              response.headers, response.fp)
    self.authenticated = True

  def _Authenticate(self):
    """Authenticates the user.

    The authentication process works as follows:
     1) We get a username and password from the user
     2) We use ClientLogin to obtain an AUTH token for the user
        (see http://code.google.com/apis/accounts/AuthForInstalledApps.html).
     3) We pass the auth token to /_ah/login on the server to obtain an
        authentication cookie. If login was successful, it tries to redirect
        us to the URL we provided.

    If we attempt to access the upload API without first obtaining an
    authentication cookie, it returns a 401 response and directs us to
    authenticate ourselves with ClientLogin.
    """
    for i in range(3):
      credentials = self.auth_function()
      try:
        auth_token = self._GetAuthToken(credentials[0], credentials[1])
      except ClientLoginError, e:
        if e.reason == "BadAuthentication":
          print >>sys.stderr, "Invalid username or password."
          continue
        if e.reason == "CaptchaRequired":
          print >>sys.stderr, (
              "Please go to\n"
              "https://www.google.com/accounts/DisplayUnlockCaptcha\n"
              "and verify you are a human.  Then try again.")
          break
        if e.reason == "NotVerified":
          print >>sys.stderr, "Account not verified."
          break
        if e.reason == "TermsNotAgreed":
          print >>sys.stderr, "User has not agreed to TOS."
          break
        if e.reason == "AccountDeleted":
          print >>sys.stderr, "The user account has been deleted."
          break
        if e.reason == "AccountDisabled":
          print >>sys.stderr, "The user account has been disabled."
          break
        if e.reason == "ServiceDisabled":
          print >>sys.stderr, ("The user's access to the service has been "
                               "disabled.")
          break
        if e.reason == "ServiceUnavailable":
          print >>sys.stderr, "The service is not available; try again later."
          break
        raise
      self._GetAuthCookie(auth_token)
      return

  def Send(self, request_path, payload=None,
           content_type="application/octet-stream",
           timeout=None,
           **kwargs):
    """Sends an RPC and returns the response.

    Args:
      request_path: The path to send the request to, eg /api/appversion/create.
      payload: The body of the request, or None to send an empty request.
      content_type: The Content-Type header to use.
      timeout: timeout in seconds; default None i.e. no timeout.
        (Note: for large requests on OS X, the timeout doesn't work right.)
      kwargs: Any keyword arguments are converted into query string parameters.

    Returns:
      The response body, as a string.
    """
    # TODO: Don't require authentication.  Let the server say
    # whether it is necessary.
    if not self.authenticated:
      self._Authenticate()

    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
      tries = 0
      while True:
        tries += 1
        args = dict(kwargs)
        url = "http://%s%s" % (self.host, request_path)
        if args:
          url += "?" + urllib.urlencode(args)
        req = self._CreateRequest(url=url, data=payload)
        req.add_header("Content-Type", content_type)
        try:
          f = self.opener.open(req)
          response = f.read()
          f.close()
          return response
        except urllib2.HTTPError, e:
          if tries > 3:
            raise
          elif e.code == 302 or e.code == 401:
            self._Authenticate()
          elif e.code >= 500 and e.code < 600:
            # Server Error - try again.
            print "server error "+str(e.code)+": sleeping and retrying..."
            time.sleep(1)
            continue
          else:
            raise
    finally:
      socket.setdefaulttimeout(old_timeout)


class HttpRpcServer(AbstractRpcServer):
  """Provides a simplified RPC-style interface for HTTP requests."""

  def _Authenticate(self):
    """Save the cookie jar after authentication."""
    super(HttpRpcServer, self)._Authenticate()
    if self.save_cookies:
      StatusUpdate("Saving authentication cookies to %s" % self.cookie_file)
      self.cookie_jar.save()

  def _GetOpener(self):
    """Returns an OpenerDirector that supports cookies and ignores redirects.

    Returns:
      A urllib2.OpenerDirector object.
    """
    opener = urllib2.OpenerDirector()
    opener.add_handler(urllib2.ProxyHandler())
    opener.add_handler(urllib2.UnknownHandler())
    opener.add_handler(urllib2.HTTPHandler())
    opener.add_handler(urllib2.HTTPDefaultErrorHandler())
    opener.add_handler(urllib2.HTTPSHandler())
    opener.add_handler(urllib2.HTTPErrorProcessor())
    if self.save_cookies:
      self.cookie_file = os.path.expanduser("~/.loadtest_cookies")
      self.cookie_jar = cookielib.MozillaCookieJar(self.cookie_file)
      if os.path.exists(self.cookie_file):
        try:
          self.cookie_jar.load()
          self.authenticated = True
          StatusUpdate("Loaded authentication cookies from %s" %
                       self.cookie_file)
        except (cookielib.LoadError, IOError):
          # Failed to load cookies - just ignore them.
          pass
      else:
        # Create an empty cookie file with mode 600
        fd = os.open(self.cookie_file, os.O_CREAT, 0600)
        os.close(fd)
      # Always chmod the cookie file
      os.chmod(self.cookie_file, 0600)
    else:
      # Don't save cookies across runs of update.py.
      self.cookie_jar = cookielib.CookieJar()
    opener.add_handler(urllib2.HTTPCookieProcessor(self.cookie_jar))
    return opener

def GetRpcServer(options):
  """Returns an instance of an AbstractRpcServer.

  Returns:
    A new AbstractRpcServer, on which RPC calls can be made.
  """

  def GetUserCredentials():
    """Prompts the user for a username and password."""
    email = options.email
    if email is None:
      email = GetEmail("Email (for capturing appengine quota details)")
    password = getpass.getpass("Password for %s: " % email)
    return (email, password)

  if options.server is None:
    options.server = "appengine.google.com"
  return HttpRpcServer(options.server, GetUserCredentials,
                          host_override=options.host,
                          save_cookies=options.save_cookies)

START_TS = None
RUNNING = False
def start_running():
  """official kickoff, i.e. after any interaction commands."""
  global RUNNING, START_TS
  RUNNING = True
  START_TS = datetime.now()

def secs_since(ts1, ts2):
  """compute seconds since start_running()."""
  delta_ts = ts2 - ts1
  return 3600*24.0*delta_ts.days + \
      1.0*delta_ts.seconds + \
      delta_ts.microseconds / 1000000.0

def perfstats(hits, pageviews):
  """computes QPS since start."""
  global START_TS
  secs_elapsed = secs_since(START_TS, datetime.now())
  hit_qps = hits / float(secs_elapsed + 0.01)
  pageview_qps = pageviews / float(secs_elapsed + 0.01)
  return (secs_elapsed, hit_qps, pageview_qps)

RESULTS = []
RESULTS_lock = thread.allocate_lock()

def append_results(res):
  RESULTS_lock.acquire()
  RESULTS.append(res)
  RESULTS_lock.release()

REQUEST_TYPES = {}
CACHE_HITRATE = {}
REQUEST_FREQ = []
def register_request_type(name, func, freq=10, cache_hitrate="50%"):
  """setup a test case.  Default to positive hitrate so we get warm vs. 
  cold cache stats.  Freq is the relative frequency for this type of
  request-- larger numbers = larger percentage for the blended results."""
  REQUEST_TYPES[name] = func
  CACHE_HITRATE[name] = int(re.sub(r'%', '', str(cache_hitrate).strip()))
  for i in range(freq):
    REQUEST_FREQ.append(name)

def disable_caching(url):
  """footprint-specific method to disable caching."""
  if url.find("?") > 0:
    # note: ?& is harmless
    return url + "&cache=0"
  else:
    return url + "?cache=0"

URLS_SEEN = {}
def make_request(cached, url):
  """actually make HTTP request."""
  if not cached:
    url = disable_caching(url)
  if url not in URLS_SEEN:
    seen_url = re.sub(re.compile("^"+OPTIONS.baseurl), '/', url)
    print "fetching "+seen_url
    URLS_SEEN[url] = True
  try:
    infh = urllib.urlopen(url)
    content = infh.read()
  except:
    print "error reading "+url
    content = ""
  return content

def search_url(base, loc="Chicago,IL", keyword="park"):
  """construct FP search URL, defaulting to [park] near [Chicago,IL]"""
  if OPTIONS.baseurl[-1] == '/' and base[0] == '/':
    url = OPTIONS.baseurl+base[1:]
  else:
    url = OPTIONS.baseurl+base
  if loc and loc != "":
    url += "&vol_loc="+loc
  if keyword and keyword != "":
    url += "&q="+keyword
  return url

def error_request(name, cached=False):
  """requests for 404 junk on the site.  Here mostly to prove that
  the framework does catch errors."""
  if make_request(cached, OPTIONS.baseurl+"foo") == "":
    return ""
  return "no content"
register_request_type("error", error_request, freq=5)

def static_url():
  """all static requests are roughly equivalent."""
  return OPTIONS.baseurl+"images/background-gradient.png"

def fp_find_embedded_objects(base_url, content):
  """cheesy little HTML parser, which also approximates browser caching
  of items on both / and /ui_snippets."""
  objs = []
  # strip newlines/etc. used in formatting
  content = re.sub(r'\s+', ' ', content)
  # one HTML element per line
  content = re.sub(r'>', '>\n', content)
  for line in content.split('\n'):
    #print "found line: "+line
    match = re.search(r'<(?:img[^>]+src|script[^>]+src|link[^>]+href)\s*=\s*(.+)',
                      line)
    if match:
      match2 = re.search(r'^["\'](.+?)["\']', match.group(1))
      url = match2.group(1)
      url = re.sub(r'[.][.]/images/', 'images/', url)
      url = urlparse.urljoin(base_url, url)
      #print "found url: "+url+"\n  on base: "+base_url
      if url not in objs:
        objs.append(url)
  return objs

static_content_request_queue = []
static_content_request_lock = thread.allocate_lock()

def fetch_static_content(base_url, content):
  """find the embedded JS/CSS/images and request them."""
  urls = fp_find_embedded_objects(base_url, content)
  static_content_request_lock.acquire()
  static_content_request_queue.extend(urls)
  static_content_request_lock.release()

def static_fetcher_main():
  """thread for fetching static content."""
  while RUNNING:
    if len(static_content_request_queue) == 0:
      time.sleep(1)
      continue
    url = None
    static_content_request_lock.acquire()
    if len(static_content_request_queue) > 0:
      url = static_content_request_queue.pop(0)
    static_content_request_lock.release()
    if url:
      # for static content, caching means client/proxy-side
      cached = (random.randint(0, 99) < OPTIONS.static_content_hitrate)
      if cached:
        continue
      ts1 = datetime.now()
      content = make_request(False, url)
      elapsed = secs_since(ts1, datetime.now())
      result_name = "static content requests"
      if content == "":
        result_name += " (errors)"
      append_results([result_name, elapsed])

def homepage_request(name, cached=False):
  """request to FP homepage."""
  content = make_request(cached, OPTIONS.baseurl)
  content += make_request(cached, search_url("/ui_snippets?", keyword=""))
  return content
register_request_type("page_home", homepage_request)

def initial_serp_request(name, cached=False):
  content = make_request(cached, search_url("/search#"))
  content += make_request(cached, search_url("/ui_snippets?"))
  return content
# don't expect much caching-- use 10% hitrate so we can see warm vs. cold stats
register_request_type("page_serp_initial", initial_serp_request, cache_hitrate="10%")

def nextpage_serp_request(name, cached=False):
  # statistically, nextpage is page 2
  # 50% hitrate due to the overfetch algorithm
  if make_request(cached, search_url("/ui_snippets?start=11")) == "":
    return ""
  # we expect next-page static content to be 100% cacheable
  # so don't return content
  return "no content"
# nextpage is relatively rare, but this includes all pagination requests
register_request_type("page_serp_next", nextpage_serp_request, freq=5)

def api_request(name, cached=False):
  # API calls are probably more likely to ask for more results and/or paginate
  if make_request(cached, search_url("/api/volopps?num=20&key=testkey")) == "":
    return ""
  # API requests don't create static content requests
  return "no content"
# until we have more apps, API calls will be rare
register_request_type("page_api", api_request, freq=2)

def setup_tests():
  request_type_counts = {}
  for name in REQUEST_FREQ:
    if name in request_type_counts:
      request_type_counts[name] += 1.0
    else:
      request_type_counts[name] = 1.0
  print "OPTIONS.baseurl: %s" % OPTIONS.baseurl
  print "OPTIONS.page_fetchers: %d" % OPTIONS.page_fetchers
  print "OPTIONS.static_fetchers: %d" % OPTIONS.static_fetchers
  print "OPTIONS.static_content_hitrate: %d%%" % OPTIONS.static_content_hitrate
  print "request type breakdown:"
  for name, cnt in request_type_counts.iteritems():
    print "  %4.1f%% - %4d%% cache hitrate - %s" % \
        (100.0*cnt/float(len(REQUEST_FREQ)), CACHE_HITRATE[name], name)

def run_tests():
  # give the threading system a chance to startup
  while RUNNING:
    testname = REQUEST_FREQ[random.randint(0, len(REQUEST_FREQ)-1)]
    func = REQUEST_TYPES[testname]
    cached = (random.randint(0, 99) < CACHE_HITRATE[testname])
    ts1 = datetime.now()
    content = func(testname, cached)
    elapsed = secs_since(ts1, datetime.now())
    if cached:
      result_name = testname + " (warm cache)"
    else:
      result_name = testname + " (cold cache)"
    # don't count static content towards latency--
    # too hard to model CSS/JS execution costs, HTTP pipelining
    # and parallel fetching.  But we do want to create load on the
    # servers
    if content and content != "":
      fetch_static_content(OPTIONS.baseurl, content)
    else:
      result_name = testname + " (errors)"
    append_results([result_name, elapsed])

def main():
  global RUNNING
  setup_tests()
  start_running()
  for i in range(OPTIONS.page_fetchers):
    thread.start_new_thread(run_tests, ())

  for i in range(OPTIONS.static_fetchers):
    thread.start_new_thread(static_fetcher_main, ())
  
  while RUNNING:
    time.sleep(2)
    pageviews = 0
    hit_reqs = len(RESULTS)
    # important to look at a snapshot-- RESULTS is appended by other threads
    for i in range(0, hit_reqs-1):
      if RESULTS[i][0].find(PAGE_NAME_PREFIX) == 0:
        pageviews += 1
    total_secs_elapsed, hit_qps, pageview_qps = perfstats(hit_reqs, pageviews)
    print " %4.1f: %d hits (%.1f hits/sec), %d pageviews (%.1f pv/sec)" % \
        (total_secs_elapsed, len(RESULTS), hit_qps, pageviews, pageview_qps)
    sum_elapsed_time = {}
    counts = {}
    for i in range(0, hit_reqs-1):
      name, elapsed_time = RESULTS[i]
      if name in sum_elapsed_time:
        sum_elapsed_time[name] += elapsed_time
        counts[name] += 1
      else:
        sum_elapsed_time[name] = elapsed_time
        counts[name] = 1
    total_counts = 0
    for name in counts:
      total_counts += counts[name]
    for name in sorted(sum_elapsed_time):
      print "  %4d requests (%4.1f%%), %6dms avg latency for %s" % \
          (counts[name], float(counts[name]*100)/float(total_counts+0.01),
           int(1000*sum_elapsed_time[name]/counts[name]), name)
    if total_secs_elapsed >= OPTIONS.run_time:
      RUNNING = False

OPTIONS = None
def get_options():
  global OPTIONS
  parser = optparse.OptionParser(usage="%prog [options]")
  # testing options
  group = parser.add_option_group("Load testing options")
  group.add_option("-r", "--run_time", type="int", default=20,
                   dest="run_time",                   
                   help="how long to run the test (seconds).")
  group.add_option("-b", "--baseurl", dest="baseurl",
                   default="footprint-loadtest.appspot.com",
                   help="server instance to test (domain).")
  group.add_option("-n", "--page_fetchers", type="int", dest="page_fetchers",
                   default=4, help="how many pageview fetchers.")
  group.add_option("--static_fetchers", type="int", dest="static_fetchers", 
                   default=3, help="how many static content fetchers.")
  group.add_option("--static_content_hitrate", type="int",
                   dest="static_content_hitrate", default=80,
                   help="client-side hitrate on static content (percent)."+
                   "note: 100 = don't simulate fetching of static content.")
  # server
  group = parser.add_option_group("Quota server options")
  group.add_option("-s", "--server", action="store", dest="server",
                   default="appengine.google.com",
                   metavar="SERVER",
                   help=("The server with the quota info. The format is host[:port]. "
                         "Defaults to 'appengine.google.com'."))
  group.add_option("-e", "--email", action="store", dest="email",
                   metavar="EMAIL", default=None,
                   help="The username to use. Will prompt if omitted.")
  group.add_option("-H", "--host", action="store", dest="host",
                   metavar="HOST", default=None,
                   help="Overrides the Host header sent with all RPCs.")
  group.add_option("--no_cookies", action="store_false",
                   dest="save_cookies", default=True,
                   help="Do not save authentication cookies to local disk.")
  OPTIONS, args = parser.parse_args(sys.argv[1:])
  if OPTIONS.baseurl[-1] != "/":
    OPTIONS.baseurl += "/"
  if not re.search("^http://", OPTIONS.baseurl):
    OPTIONS.baseurl = "http://" + OPTIONS.baseurl

def get_quota_details():
  global OPTIONS
  rpc_server = GetRpcServer(OPTIONS)
  response_body = rpc_server.Send("/dashboard/quotadetails",
                                  app_id="footprint-loadtest")
  # get everything onto one line for easy parsing
  content = re.sub("\n", " ", response_body)
  content = re.sub("\s+", " ", content)
  content = re.sub("> <", "><", content)
  content = re.sub("<h3>", "\n<h3>", content)
  details = {}
  for line in content.split("\n"):
    for header in re.finditer("<h3>(.+?)</h3>", line):
      category = header.group(1)
      for match in re.finditer('<tr><td>([a-zA-Z ]+)</td><td>.+?'+
                               '>\s*([0-9.+-]+) of ([0-9.+-]+)( [a-zA-Z0-9 ]+ )?',
                               line):
        name = match.group(1)
        value = float(match.group(2))
        quota = float(match.group(3))
        units = match.group(4)
        if units == None:
          units = ""
        else:
          units = units.strip()
        if name != category:
          name = re.sub(re.compile(category+"\s*"), r'', name)
        details[category+"."+name] = [value, quota, units]
          
  return details

def fmtnum(num):
  """add commas to a float."""
  num = str(num)
  while True:
    oldnum = num
    num = re.sub(r'(\d)(\d\d\d[^\d])', r'\1,\2', oldnum)
    if oldnum == num:
      break
  num = re.sub(r'([.]\d\d)\d+$', r'\1', num)
  num = re.sub(r'[.]0+$', r'', num)
  return num

if __name__ == "__main__":
  #logging.getLogger().setLevel(logging.DEBUG)
  get_options()
  start_details = get_quota_details()
  main()
  end_details = get_quota_details()
  for key in start_details:
    startval = start_details[key][0]
    endval = end_details[key][0]
    quota = end_details[key][1]
    units = end_details[key][2]
    delta = endval - startval
    day_delta = 86400.0 / OPTIONS.run_time * delta
    if quota > 0.0:
      delta_pct = "%.1f%%" % (100.0 * day_delta / quota)
    else:
      delta_pct = "0.0%"
    if delta < 0.0001:
      continue
    print "%45s: %6s of quota: %s used, which scales to %s of %s %s / day." % \
        (key, delta_pct, fmtnum(delta), fmtnum(day_delta), fmtnum(quota), units)

