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
views in the app, in the MVC sense.
"""
# note: view classes aren inherently not pylint-compatible
# pylint: disable-msg=C0103
# pylint: disable-msg=W0232
# pylint: disable-msg=E1101
# pylint: disable-msg=R0903
from datetime import datetime
import cgi
import email.Utils
import os
import urllib
import logging
import re
import time

from versioned_memcache import memcache
from google.appengine.api import urlfetch
from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

from fastpageviews import pagecount
from third_party.recaptcha.client import captcha

import api
import solr_search
import deploy
import geocode
import models
import modelutils
import posting
import search
import urls
import userinfo
import utils
import view_helper
import searchresult

TEMPLATE_DIR = 'templates/'

HOMEPAGE_TEMPLATE = 'homepage.html'
TEST_PAGEVIEWS_TEMPLATE = 'test_pageviews.html'
SEARCH_RESULTS_TEMPLATE = 'search_results.html'
SEARCH_RESULTS_DEBUG_TEMPLATE = 'search_results_debug.html'
SEARCH_RESULTS_RSS_TEMPLATE = 'search_results.rss'
SEARCH_RESULTS_MISSING_KEY_TEMPLATE = 'search_results_missing_key.html'
SNIPPETS_LIST_TEMPLATE = 'snippets_list.html'
SNIPPETS_LIST_MINI_TEMPLATE = 'snippets_list_mini.html'
SNIPPETS_LIST_RSS_TEMPLATE = 'snippets_list.rss'
MY_EVENTS_TEMPLATE = 'my_events.html'
POST_TEMPLATE = 'post.html'
POST_RESULT_TEMPLATE = 'post_result.html'
ADMIN_TEMPLATE = 'admin.html'
DATAHUB_DASHBOARD_TEMPLATE = 'datahub_dashboard.html'
MODERATE_TEMPLATE = 'moderate.html'
STATIC_CONTENT_TEMPLATE = 'static_content.html'
NOT_FOUND_TEMPLATE = 'not_found.html'
SPEC_TEMPLATE = 'spec.html'

DASHBOARD_BASE_URL = "http://google1.osuosl.org/~footprint/datahub/dashboard/"
DATAHUB_LOG = DASHBOARD_BASE_URL + "load_gbase.log.bz2"

DEFAULT_NUM_RESULTS = 10

# Register custom Django templates
template.register_template_library('templatetags.comparisonfilters')
template.register_template_library('templatetags.stringutils')
template.register_template_library('templatetags.dateutils_tags')


# TODO: not safe vs. spammers to checkin... but in our design,
# the worst that happens is a bit more spam in our moderation
# queue, i.e. no real badness, just slightly longer review
# cycle until we can regen a new key.  Meanwhile, avoiding this
# outright is a big pain for launch, regen is super easy and
# it could be a year+ before anybody notices.  Note: the varname
# is intentionally boring, to avoid accidental discovery by
# code search tools.
PK = "6Le2dgUAAAAAABp1P_NF8wIUSlt8huUC97owQ883"


def get_unique_args_from_request(request):
  """ Gets unique args from a request.arguments() list.
  If a URL search string contains a param more than once, only
  the last value is retained.
  For example, for the query "http://foo.com/?a=1&a=2&b=3"
  this function would return { 'a': '2', 'b': '3' }

  Args:
    request: A list given by webapp.RequestHandler.request.arguments()
  Returns:
    dictionary of URL parameters.
  """
  args = request.arguments()
  unique_args = {}
  for arg in args:
    allvals = request.get_all(arg)
    unique_args[arg] = allvals[len(allvals)-1]
  return unique_args

def optimize_page_speed(request):
  """OK to optimize the page: minimize CSS, minimize JS, Sprites, etc."""
  # page_optim=1 forces optimization
  page_optim = request.get('page_optim')
  if page_optim == "1":
    return True
  # page_debug=1 forces no optimization
  page_debug = request.get('page_debug')
  if page_debug == "1":
    return False
  # optimize in production and on appspot
  if (request.host_url.find("appspot.com") >= 0 or
      request.host_url.find("allforgood.org") >= 0):
    return True
  return False

def get_default_template_values(request, current_page):
  # for debugging login issues
  no_login = (request.get('no_login') == "1")

  version = request.get('dbgversion')
  # don't allow junk
  if not version or not re.search(r'^[0-9a-z._-]+$', version):
    version = os.getenv('CURRENT_VERSION_ID')

  template_values = {
    'user' : userinfo.get_user(request),
    'current_page' : current_page,
    'host' : urllib.quote(request.host_url),
    'path' : request.path,
    'version' : version,
    'no_login' : no_login,
    'optimize_page' : optimize_page_speed(request),
    'view_url': request.url,
    }
  load_userinfo_into_dict(template_values['user'], template_values)
  return template_values

def load_userinfo_into_dict(user, userdict):
  """populate the given dict with user info."""
  if user:
    userdict["user"] = user
    userdict["user_days_since_joined"] = (datetime.now() -
                                          user.get_user_info().first_visit).days
  else:
    userdict["user"] = None
    userdict["user_days_since_joined"] = None

def render_template(template_filename, template_values):
  """wrapper for template.render() which handles path."""
  path = os.path.join(os.path.dirname(__file__),
                      TEMPLATE_DIR + template_filename)
  deploy.load_standard_template_values(template_values)
  rendered = template.render(path, template_values)
  return rendered


def require_moderator(handler_method):
  """Decorator ensuring the current FP user is a logged in moderator.

  Also sets self.user.
  """
  def decorate(self):
    if not getattr(self, 'user', None):
      self.user = userinfo.get_user(self.request)
    if not self.user:
      self.error(401)
      self.response.out.write('<html><body>Please log in.</body></html>')
      return
    if (not self.user.get_user_info() or
        not self.user.get_user_info().moderator):
      self.error(403)
      self.response.out.write('<html><body>Permission denied.</body></html>')
      logging.warning('Non-moderator blacklist attempt.')
      return
    return handler_method(self)
  return decorate

def require_usig(handler_method):
  """Deceratore ensuring the current FP user has a valid usig XSRF token.

  Also sets self.usig and self.user."""
  def decorate(self):
    if not getattr(self, 'user', None):
      self.user = userinfo.get_user(self.request)
    self.usig = userinfo.get_usig(self.user)
    if self.usig != self.request.get('usig'):
      self.error(403)
      logging.warning('XSRF attempt. %s!=%s',
                      self.usig, self.request.get('usig'))
      return
    return handler_method(self)
  return decorate


def require_admin(handler_method):
  """Decorator ensuring the current App Engine user is an administrator."""
  def decorate(self):
    """Validate request is from an admin user, send to logon page if not."""
    user = users.get_current_user()

    if user:
      if users.is_current_user_admin():
        # User is an admin, go ahead and run the handler
        return handler_method(self)

      else:
        # User is not an admin, return unauthorized
        self.error(401)
        html = '<html><body>'
        html += 'Sorry, you are not an administrator. Please '
        html += '<a href="%s">' % users.create_logout_url(self.request.url)
        html += 'log out</a> and sign in as an administrator.'
        html += '</body></html>'
        self.response.out.write(html)
        return

    # No user, redirect to the login page
    self.redirect(users.create_login_url(self.request.url))
    return

  return decorate


def expires(seconds):
  """Set expires and cache-control headers appropriately."""
  # If you try to use '@expires' instead of '@expires(0)', this
  # will raise an exception.
  seconds = int(seconds)
  def decorator(handler_method):
    def decorate(self):
      if seconds <= 0:
        # Expire immediately.
        self.response.headers['Cache-Control'] = 'no-cache'
        self.response.headers['Expires'] = 'Thu, 01 Jan 2009 00:00:00 GMT'
        pass
      else:
        self.response.headers['Cache-Control'] = 'public'
        self.response.headers['Expires'] = email.Utils.formatdate(
            time.time() + seconds, usegmt=True)
      # The handler method can now re-write these if needed.
      return handler_method(self)
    return decorate
  return decorator


class test_page_views_view(webapp.RequestHandler):
  """testpage for pageviews counter."""
  @expires(0)
  def get(self):
    """HTTP get method."""
    pagename = "testpage%s" % (self.request.get('pagename'))
    pc = pagecount.IncrPageCount(pagename, 1)
    template_values = pagecount.GetStats()
    template_values["pagename"] = pagename
    template_values["pageviews"] = pc
    self.response.out.write(render_template(TEST_PAGEVIEWS_TEMPLATE,
                                           template_values))

class home_page_view(webapp.RequestHandler):
  """default homepage for consumer UI."""
  @expires(0)  # User specific.
  def get(self):
    """HTTP get method."""
    template_values = get_default_template_values(self.request, 'HOMEPAGE')
    self.response.out.write(render_template(HOMEPAGE_TEMPLATE,
                                           template_values))

class home_page_redir_view(webapp.RequestHandler):
  """handler for /home, which somehow got indexed by google."""
  @expires(0)
  def get(self):
    """HTTP get method."""
    self.redirect("/")

class not_found_handler(webapp.RequestHandler):
  def get(self):
    self.error(404)
    template_values = get_default_template_values(self.request, 'STATIC_PAGE')
    self.response.out.write(render_template(NOT_FOUND_TEMPLATE,
                                            template_values))
		
class consumer_ui_search_redir_view(webapp.RequestHandler):
  """handler for embedded HTML forms, which can't form queries
     with query params to the right of the # (hash)."""
  @expires(0)
  def get(self):
    """HTTP get method."""
    # replace the path and replace the ? with #
    # down the road, if the consumer UI diverges from the urlparams
    # required by HTML embedders, then this algorithm could become
    # more complex, possibly including real page(s) instead of a 
    # simple reuse of the consumer UI.
    dest = urls.URL_CONSUMER_UI_SEARCH + "#" + self.request.query_string
    self.redirect(dest)

class consumer_ui_search_view(webapp.RequestHandler):
  """default homepage for consumer UI."""
  @expires(0)  # User specific.
  def get(self):
    """HTTP get method."""
    template_values = get_default_template_values(self.request, 'SEARCH')
    template_values['result_set'] = {}
    template_values['is_main_page'] = True
    self.response.out.write(render_template(SEARCH_RESULTS_TEMPLATE,
                                            template_values))

class spec_view(webapp.RequestHandler):
  """view fpxml spec documentation"""
  @expires(0)  # User specific.
  def get(self):
    """HTTP get method."""
    template_values = get_default_template_values(self.request, 'SPEC')
    self.response.out.write(render_template(SPEC_TEMPLATE,
                                            template_values))

class search_view(webapp.RequestHandler):
  """run a search from the API.  note various output formats."""
  @expires(1800)  # Search results change slowly; cache for half an hour.
  def get(self):
    """HTTP get method."""
    unique_args = get_unique_args_from_request(self.request)

    if "key" not in unique_args:
      tplresult = render_template(SEARCH_RESULTS_MISSING_KEY_TEMPLATE, {})
      self.response.out.write(tplresult)
      pagecount.IncrPageCount("key.missing", 1)
      return
    pagecount.IncrPageCount("key.%s.searches" % unique_args["key"], 1)
    result_set = search.search(unique_args)

    # insert the interest data-- API searches are anonymous, so set the user
    # interests to 'None'.  Note: left here to avoid polluting searchresults.py
    # with view_helper.py and social/personalization stuff.
    opp_ids = []
    # perf: only get interest counts for opps actually in the clipped results
    for primary_res in result_set.clipped_results:
      opp_ids += [result.item_id for result in primary_res.merged_list]
    others_interests = view_helper.get_interest_for_opportunities(opp_ids)
    view_helper.annotate_results(None, others_interests, result_set)
    # add-up the interests from the children
    for primary_res in result_set.clipped_results:
      for result in primary_res.merged_list:
        primary_res.interest_count += result.interest_count

    result_set.request_url = self.request.url

    output = None
    if api.PARAM_OUTPUT in unique_args:
      output = unique_args[api.PARAM_OUTPUT]

    if not output or output == "html":
      if "geocode_responses" not in unique_args:
        unique_args["geocode_responses"] = 1
      tpl = SEARCH_RESULTS_DEBUG_TEMPLATE
    elif output == "rss":
      self.response.headers["Content-Type"] = "application/rss+xml"
      tpl = SEARCH_RESULTS_RSS_TEMPLATE
    elif output == "csv":
      # TODO: implement SEARCH_RESULTS_CSV_TEMPLATE
      tpl = SEARCH_RESULTS_RSS_TEMPLATE
    elif output == "tsv":
      # TODO: implement SEARCH_RESULTS_TSV_TEMPLATE
      tpl = SEARCH_RESULTS_RSS_TEMPLATE
    elif output == "xml":
      # TODO: implement SEARCH_RESULTS_XML_TEMPLATE
      #tpl = SEARCH_RESULTS_XML_TEMPLATE
      tpl = SEARCH_RESULTS_RSS_TEMPLATE
    elif output == "rssdesc":
      # TODO: implement SEARCH_RESULTS_RSSDESC_TEMPLATE
      tpl = SEARCH_RESULTS_RSS_TEMPLATE
    else:
      # TODO: implement SEARCH_RESULTS_ERROR_TEMPLATE
      # TODO: careful about escapification/XSS
      tpl = SEARCH_RESULTS_DEBUG_TEMPLATE

    latlng_string = ""
    if "lat" in result_set.args and "long" in result_set.args:
      latlng_string = "%s,%s" % (result_set.args["lat"],
                                 result_set.args["long"])
    logging.debug("geocode("+result_set.args[api.PARAM_VOL_LOC]+") = "+
                  result_set.args["lat"]+","+result_set.args["long"])
    template_values = get_default_template_values(self.request, 'SEARCH')
    template_values.update({
        'result_set': result_set,
        # TODO: remove this stuff...
        'latlong': latlng_string,
        'keywords': result_set.args[api.PARAM_Q],
        'location': result_set.args[api.PARAM_VOL_LOC],
        'max_distance': result_set.args[api.PARAM_VOL_DIST],
      })

    # pagecount.GetPageCount() is expensive-- only do for debug mode,
    # where this is printed.
    if tpl == SEARCH_RESULTS_DEBUG_TEMPLATE:
      for res in result_set.clipped_results:
        res.merged_clicks = pagecount.GetPageCount(
          pagecount.CLICKS_PREFIX+res.merge_key)
        if res.merged_impressions < 1.0:
          res.merged_ctr = "0"
        else:
          res.merged_ctr = "%.2f" % (
            100.0 * float(res.merged_clicks) / float(res.merged_impressions))

    self.response.out.write(render_template(tpl, template_values))


class ui_snippets_view(webapp.RequestHandler):
  """run a search and return consumer HTML for the results--
  this awful hack exists for latency reasons: it's super slow to
  parse things on the client."""
  @expires(0)  # User specific.
  def get(self):
    """HTTP get method."""
    unique_args = get_unique_args_from_request(self.request)
    result_set = search.search(unique_args)
    result_set.request_url = self.request.url
    template_values = get_default_template_values(self.request, 'SEARCH')

    # Retrieve the user-specific information for the search result set.
    user = template_values['user']
    if user:
      template_values['moderator'] = user.get_user_info().moderator
      result_set = view_helper.get_annotated_results(user, result_set)
      view_data = view_helper.get_friends_data_for_snippets(user)
    else:
      template_values['moderator'] = False
      view_data = {
        'friends': [],
        'friends_by_event_id_js': '{}',
      }

    loc = unique_args.get(api.PARAM_VOL_LOC, None)
    if loc and not geocode.is_latlong(loc) and not geocode.is_latlongzoom(loc):
      template_values['query_param_loc'] = loc
    else:
      template_values['query_param_loc'] = None

    template_values.update({
        'result_set': result_set,
        'has_results' : (result_set.num_merged_results > 0),  # For django.
        'last_result_index' : result_set.estimated_results,
        'display_nextpage_link' : result_set.has_more_results,
        'friends' : view_data['friends'],
        'friends_by_event_id_js': view_data['friends_by_event_id_js'],
        'query_param_q' : unique_args.get(api.PARAM_Q, None),
        'full_list' : self.request.get('minimal_snippets_list') != '1',
      })

    if self.request.get('minimal_snippets_list'):
      # Minimal results list for homepage.
      result_set.clipped_results.sort(cmp=searchresult.compare_result_dates)
      self.response.out.write(render_template(SNIPPETS_LIST_MINI_TEMPLATE,
                                              template_values))
    else:
      self.response.out.write(render_template(SNIPPETS_LIST_TEMPLATE,
                                              template_values))

class ui_my_snippets_view(webapp.RequestHandler):
  """The current spec for the My Events view (also known as "Profile")
  defines the following filters:
  * Filter on my own events
  * Filter on my own + my friends's events
  * Filter on various relative time periods
  * Filter on events that are still open (not past their completion dates)

  Furthermore the UI is spec'd such that each event displays a truncated list
  of friend names, along with a total count of friends.

  In order to collect that info, we seem to be stuck with O(n2) because
  I need to know *all* the events that *all* of my friends are interested in:
  1. Get the list of all events that I like or am doing.
  2. Get the list of all my friends.
  3. For each of my friends, get the list of all events that that friend likes
  or is doing.
  4. For each of the events found in step (3), associate the list of all
  interested users with that event.
  """
  @expires(0)  # User specific.
  def get(self):
    """HTTP get method."""
    template_values = get_default_template_values(self.request, 'MY_EVENTS')
    user_info = template_values['user']

    unique_args = get_unique_args_from_request(self.request)

    if user_info:
      # Get the list of all events that I like or am doing.
      # This is a dict of event id keys and interest flag values (right now
      # we only support Liked).
      (my_interests, ordered_event_ids) = \
          view_helper.get_user_interests(user_info, True)
      
      # Fetch the event details for the events I like, so they can be
      # displayed in the snippets template.
      my_events_gbase_result_set = solr_search.get_from_ids(ordered_event_ids)
      for result in my_events_gbase_result_set.results:
        result.interest = my_interests.get(result.item_id, 0)

      search.normalize_query_values(unique_args)
      start = unique_args[api.PARAM_START]
      my_events_gbase_result_set.clip_start_index = start
      num = unique_args[api.PARAM_NUM]

      # Handle clipping.
      my_events_gbase_result_set.clip_results(start, num)

      # Get general interest numbers (i.e., not filtered to friends).
      overall_stats_for_my_interests = \
        view_helper.get_interest_for_opportunities(my_interests)
      view_helper.annotate_results(my_interests,
                                   overall_stats_for_my_interests,
                                   my_events_gbase_result_set)

      friend_data = view_helper.get_friends_data_for_snippets(user_info)
      template_values.update({
          'result_set': my_events_gbase_result_set,
          'has_results' : len(my_events_gbase_result_set.clipped_results) > 0,
          'last_result_index':
            my_events_gbase_result_set.clip_start_index + \
            len(my_events_gbase_result_set.clipped_results),
          'display_nextpage_link' : my_events_gbase_result_set.has_more_results,
          'friends' : friend_data['friends'],
          'friends_by_event_id_js': friend_data['friends_by_event_id_js'],
          'like_count': len(my_interests),
        })
    else:
      template_values.update({ 'has_results' : False, })

    template_values['query_param_q'] = unique_args.get(api.PARAM_Q, None)
    loc = unique_args.get(api.PARAM_VOL_LOC, None)
    if not geocode.is_latlong(loc) and not geocode.is_latlongzoom(loc):
      template_values['query_param_loc'] = loc

    self.response.out.write(render_template(SNIPPETS_LIST_TEMPLATE,
                                            template_values))

class my_events_view(webapp.RequestHandler):
  """Shows events that you and your friends like or are doing."""
  @expires(0)  # User specific.
  def get(self):
    """HTTP get method."""
    template_values = get_default_template_values(self.request, 'MY_EVENTS')
    if not template_values['user']:
      template_values = {
        'current_page': 'MY_EVENTS',
        # Don't bother rendering this page if not authenticated.
        'redirect_to_home': True,
      }
      self.response.out.write(render_template(MY_EVENTS_TEMPLATE,
          template_values))
      return
    self.response.out.write(render_template(MY_EVENTS_TEMPLATE,
                                            template_values))

class post_view(webapp.RequestHandler):
  """user posting flow."""

  @expires(0)
  def post(self):
    """HTTP post method."""
    return self.get()

  @expires(0)
  def get(self):
    """HTTP get method."""
    user_info = userinfo.get_user(self.request)

    # synthesize GET method url from either GET or POST submission
    geturl = self.request.path + "?"
    for arg in self.request.arguments():
      geturl += urllib.quote_plus(arg) + "=" + \
          urllib.quote_plus(self.request.get(arg)) + "&"
    template_values = {
      'current_page' : 'POST',
      'geturl' : geturl,
      }
    load_userinfo_into_dict(user_info, template_values)

    resp = None
    recaptcha_challenge_field = self.request.get('recaptcha_challenge_field')
    if not recaptcha_challenge_field:
      self.response.out.write(render_template(POST_TEMPLATE, template_values))
      return

    recaptcha_response_field = self.request.get('recaptcha_response_field')
    resp = captcha.submit(recaptcha_challenge_field, recaptcha_response_field,
                          PK, self.request.remote_addr)
    vals = {}
    computed_vals = {}
    recaptcha_response = self.request.get('recaptcha_response_field')
    if (resp and resp.is_valid) or recaptcha_response == "test":
      vals["user_ipaddr"] = self.request.remote_addr
      load_userinfo_into_dict(user_info, vals)
      for arg in self.request.arguments():
        vals[arg] = self.request.get(arg)
      respcode, item_id, content = posting.create_from_args(vals, computed_vals)
      # TODO: is there a way to reference a dict-value in appengine+django ?
      for key in computed_vals:
        template_values["val_"+str(key)] = str(computed_vals[key])
      template_values["respcode"] = str(respcode)
      template_values["id"] = str(item_id)
      template_values["content"] = str(content)
    else:
      template_values["respcode"] = "401"
      template_values["id"] = ""
      template_values["content"] = "captcha error, e.g. response didn't match"

    template_values["vals"] = vals
    for key in vals:
      keystr = "val_"+str(key)
      if keystr in template_values:
        # should never happen-- throwing a 500 avoids silent failures
        self.response.set_status(500)
        self.response.out.write("internal error: duplicate template key")
        logging.error("internal error: duplicate template key: "+keystr)
        return
      template_values[keystr] = str(vals[key])
    self.response.out.write(render_template(POST_RESULT_TEMPLATE,
                                            template_values))


class admin_view(webapp.RequestHandler):
  """admin UI."""
  @require_admin
  @expires(0)
  def get(self):
    """HTTP get method."""

    # XSRF check: usig = signature of the user's login cookie.
    # Note: This is the logged in app engine user and uses
    # an internal implementation detail of appengine.
    usig = utils.signature(userinfo.get_cookie('ACSID') or
                           userinfo.get_cookie('dev_appserver_login'))
    template_values = {
      'logout_link': users.create_logout_url('/'),
      'msg': '',
      'action': '',
      'usig': usig,
      'version' : os.getenv('CURRENT_VERSION_ID'),
    }

    action = self.request.get('action')
    if not action:
      action = "mainmenu"
    template_values['action'] = action

    if action == "mainmenu":
      template_values['msg'] = ""
    elif action == "flush_memcache":
      memcache.flush_all()
      template_values['msg'] = "memcached flushed"
    elif action == 'moderators':
      self.admin_moderator(template_values)
    logging.debug("admin_view: %s" % template_values['msg'])
    self.response.out.write(render_template(ADMIN_TEMPLATE,
                                            template_values))

  def admin_moderator(self, template_values):
    """View for adding/deleting moderators."""

    # TODO: Use the template!
    message = []
    message.append('<h2>Moderator Management</h2>')

    moderator_query = models.UserInfo.gql('WHERE moderator = TRUE')
    request_query = models.UserInfo.gql('WHERE moderator = FALSE and ' +
                                        'moderator_request_email > \'\'')

    message.append('<form method="POST">'
        '<input type="hidden" name="usig" value="%s">'
        '<input type="hidden" name="action" value="moderators">' %
        template_values['usig'])
    message.append('Existing moderators'
        '<table><tr><td>+</td><td>-</td><td>UID</td><td>Email</td></tr>')
    for moderator in moderator_query:
      keyname = moderator.key().name() or ''
      desc = moderator.moderator_request_desc or ''
      email = moderator.moderator_request_email or ''
      message.append('<tr><td>&nbsp;</td><td>'
          '<input type="checkbox" name="disable" value="%s"></td><td>%s</td>'
          '<td><span title="%s">%s</span></td></tr>' %
          (cgi.escape(keyname, True), cgi.escape(keyname),
           cgi.escape(desc, True), cgi.escape(email)))

    message.append('</table>Requests<table>'
                   '<tr><td>+</td><td>-</td>'
                   '<td>UID</td><td>Email</td></tr>')
    for request in request_query:
      keyname = request.key().name() or ''
      desc = request.moderator_request_desc or ''
      email = request.moderator_request_email or ''
      message.append('<tr><td>'
          '<input type="checkbox" name="enable" value="%s"></td>'
          '<td>&nbsp;</td>'
          '<td>%s</td><td><span title="%s">%s</span></td></tr>' %
          (cgi.escape(keyname, True), cgi.escape(keyname, True),
           cgi.escape(desc, True), cgi.escape(email, True)))

    message.append('</table>'
                   '<input type="submit" />'
                   '</form>')

    message.append('<hr>')
    template_values['msg'] = ''.join(message)

  @require_admin
  def post(self):
    """HTTP post method."""
    if self.request.get('action') != 'moderators':
      self.error(400)
      return
    usig = utils.signature(userinfo.get_cookie('ACSID') or
                           userinfo.get_cookie('dev_appserver_login'))
    if self.request.get('usig') != usig:
      self.error(400)
      logging.warning('XSRF attempt. %s!=%s', usig, self.request.get('usig'))
      return

    keys_to_enable = self.request.POST.getall('enable')
    keys_to_disable = self.request.POST.getall('disable')

    now = datetime.isoformat(datetime.now())
    admin = users.get_current_user().email()

    users_to_enable = models.UserInfo.get_by_key_name(keys_to_enable)
    for user in users_to_enable:
      user.moderator = True
      if not user.moderator_request_admin_notes:
        user.moderator_request_admin_notes = ''
      user.moderator_request_admin_notes += '%s: Enabled by %s.\n' % \
          (now, admin)
    db.put(users_to_enable)

    users_to_disable = models.UserInfo.get_by_key_name(keys_to_disable)
    for user in users_to_disable:
      user.moderator = False
      if not user.moderator_request_admin_notes:
        user.moderator_request_admin_notes = ''
      user.moderator_request_admin_notes += '%s: Disabled by %s.\n' % \
          (now, admin)
    db.put(users_to_disable)

    self.response.out.write(
        '<div style="color: green">Enabled %s and '
        'disabled %s moderators.</div>' %
        (len(users_to_enable), len(users_to_disable)))
    self.response.out.write('<a href="%s?action=moderators&zx=%d">'
        'Continue</a>' % (self.request.path_url, datetime.now().microsecond))


class redirect_view(webapp.RequestHandler):
  """Process redirects. Present an interstital if the url is not signed."""
  @expires(0)  # Used for counting.
  def get(self):
    """HTTP get method."""
    # destination url
    url = self.request.get('q')
    if not url or (not url.startswith('http:') and
                   not url.startswith('https:')):
      self.error(400)
      return
    # id is optional -- for tracking clicks on individual items
    id = self.request.get('id')
    if not id:
      id = ""
    sig = self.request.get('sig')
    expected_sig = utils.signature(url+id)
    logging.debug('url: %s s: %s xs: %s' % (url, sig, expected_sig))
    if sig == expected_sig:
      if id:
        # note: testapi calls don't test clicks...
        clicks = pagecount.IncrPageCount(pagecount.CLICKS_PREFIX + id, 1)
        # note: clicks are relatively rare-- we can trivially afford the
        # cost of CTR computation, and it helps development.
        views = pagecount.GetPageCount(pagecount.VIEWS_PREFIX + id)
        logging.debug("click: merge_key=%s  clicks=%d  views=%d  ctr=%.1f%%" %
                      (id, clicks, views, float(clicks)/float(views+0.1)))
      self.redirect(url)
      return

    # TODO: Use a proper template so this looks nicer.
    response = ('<h1>Redirect</h1>' +
                'This page is sending you to <a href="%s">%s</a><p />' %
                (cgi.escape(url, True), cgi.escape(url, True)))
    # TODO: Something more clever than go(-1), which doesn't work on new
    # windows, etc. Maybe check for 'referer' or send users to '/'.
    response += ('If you do not want to visit that page, you can ' +
                '<a href="javascript:history.go(-1)">go back</a>.')
    self.response.out.write(response)

class moderate_view(webapp.RequestHandler):
  """fast UI for voting/moderating on listings."""

  @require_moderator
  @expires(0)
  def get(self):
    """HTTP get method."""
    return self.moderate_postings(False)

  @require_moderator
  @require_usig
  def post(self):
    """HTTP post method."""
    return self.moderate_postings(True)

  def moderate_postings(self, is_post):
    """Combined request handler. Only POSTs can modify state."""
    action = self.request.get('action')
    if action == "test":
      posting.createTestDatabase()

    now = datetime.now()
    nowstr = now.strftime("%Y-%m-%d %H:%M:%S")
    if is_post:
      ts = self.request.get('ts', nowstr)
      dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
      delta = now - dt
      if delta.seconds < 3600:
        logging.debug("processing changes...")
        vals = {}
        for arg in self.request.arguments():
          vals[arg] = self.request.get(arg)
        posting.process(vals)

    num = self.request.get('num', "20")
    reslist = posting.query(num=int(num))
    def compare_quality_scores(s1, s2):
      """compare two quality scores for the purposes of sorting."""
      diff = s2.quality_score - s1.quality_score
      if (diff > 0):
        return 1
      if (diff < 0):
        return -1
      return 0
    reslist.sort(cmp=compare_quality_scores)
    for i, res in enumerate(reslist):
      res.idx = i+1
      if res.description > 100:
        res.description = res.description[0:97]+"..."

    template_values = get_default_template_values(self.request, 'MODERATE')
    template_values.update({
        'num' : str(num),
        'ts' : str(nowstr),
        'result_set' : reslist,
        'usig' : userinfo.get_usig(self.user)
        })
    self.response.out.write(render_template(MODERATE_TEMPLATE, template_values))

class moderate_blacklist_view(webapp.RequestHandler):
  """Handle moderating blacklist entries."""
  @require_moderator
  @expires(0)
  def get(self):
    """HTTP get method for blacklist actions."""
    action = self.request.get('action')
    if action not in ['blacklist', 'unblacklist']:
      self.error(400)
      return

    key = self.request.get('key')
    if not key:
      self.error(400)
      self.response.out.write("<html><body>sorry: key required</body></html>")
      return


    def generate_blacklist_form(action, key):
      """Return an HTML form for the blacklist action."""
      # TODO: This should obviously be in a template.
      usig = userinfo.get_usig(self.user)
      return ('<form method="POST" action="%s">'
              '<input type="hidden" name="action" value="%s">'
              '<input type="hidden" name="usig" value="%s">'
              '<input type="hidden" name="key" value="%s">'
              '<input type="submit" value="I am sure">'
              '</form>' %
              (self.request.path_url, action, usig, key))

    text = 'Internal error.'
    opp_stats = modelutils.get_by_ids(models.VolunteerOpportunityStats,
                                      [key])
    key_blacklisted = key in opp_stats and opp_stats[key].blacklisted


    if action == "blacklist" and not key_blacklisted:
      text = ('Please confirm blacklisting of key %s: %s' %
              (key, generate_blacklist_form('blacklist', key)))
    elif action == 'unblacklist' and not key_blacklisted:
      text = 'Key %s is not currently blacklisted.' % key
    else:
      text = ('key %s is already blacklisted.<br>'
              'Would you like to restore it?%s' %
              (key, generate_blacklist_form('unblacklist', key)))

    # TODO: Switch this to its own template!
    template_values = {
        'user' : self.user,
        'path' : self.request.path,
        'static_content' : text,
    }
    self.response.out.write(render_template(STATIC_CONTENT_TEMPLATE,
                                            template_values))

  @require_moderator
  @require_usig
  @expires(0)
  def post(self):
    """Handle edits to the blacklist from HTTP POST."""
    action = self.request.get('action')
    if action not in ['blacklist', 'unblacklist']:
      self.error(400)
      return

    key = self.request.get('key')
    if not key:
      self.error(400)
      self.response.out.write("<html><body>sorry: key required</body></html>")
      return

    if self.request.get('action') == 'blacklist':
      if not models.VolunteerOpportunityStats.set_blacklisted(key, 1):
        text = 'Internal failure trying to add key %s to blacklist.' % key
      else:
        # TODO: better workflow, e.g. email the deleted key to an address
        # along with an url to undelete it?
        # Or just show it on the moderate/action=unblacklist page.
        undel_url = '%s?action=unblacklist&key=%s' % (self.request.path_url,
                                                      key)
        text = ('deleted listing with key %s.<br/>'
                'To undo, click <a href="%s">here</a>'
                ' (you may want to save this URL).' %
                (key, undel_url))
    else:
      if not models.VolunteerOpportunityStats.set_blacklisted(key, 0):
        text = 'Internal failure trying to remove key %s from blacklist.' % key
      else:
        text = "un-deleted listing with key "+key

    # TODO: Switch this to its own template!
    template_values = {
        'user' : self.user,
        'path' : self.request.path,
        'static_content' : text,
    }
    self.response.out.write(render_template(STATIC_CONTENT_TEMPLATE,
                                            template_values))


class action_view(webapp.RequestHandler):
  """vote/tag/etc on a listing.  TODO: rename to something more specific."""
  @expires(0)
  def post(self):
    """HTTP POST method."""
    if self.request.get('type') != 'star':
      self.error(400)  # Bad request
      return

    user = userinfo.get_user(self.request)
    opp_id = self.request.get('oid')
    base_url = self.request.get('base_url')
    new_value = self.request.get('i')

    if not user:
      logging.warning('No user.')
      self.error(401)  # Unauthorized
      return

    if not opp_id or not base_url or not new_value:
      logging.warning('bad param')
      self.error(400)  # Bad request
      return

    new_value = int(new_value)
    if new_value != 0 and new_value != 1:
      self.error(400)  # Bad request
      return

    xsrf_header_found = False
    for h, v in self.request.headers.iteritems():
      if h.lower() == 'x-requested-with' and v == 'XMLHttpRequest':
        xsrf_header_found = True
        break

    if not xsrf_header_found:
      self.error(400)
      logging.warning('Attempted XSRF.')
      return

    user_entity = user.get_user_info()
    user_interest = models.UserInterest.get_or_insert(
      models.UserInterest.make_key_name(user_entity, opp_id),
      user=user_entity, opp_id=opp_id, liked_last_modified=datetime.now())

    if not user_interest:
      self.error(500)  # Server error.
      return

    # Populate VolunteerOpportunity table with (opp_id,base_url)
    # TODO(paul): Populate this more cleanly and securely, not from URL params.
    key = models.VolunteerOpportunity.DATASTORE_PREFIX + opp_id
    info = models.VolunteerOpportunity.get_or_insert(key)
    if info.base_url != base_url:
      info.base_url = base_url
      info.last_base_url_update = datetime.now()
      info.base_url_failure_count = 0
      info.put()

    # pylint: disable-msg=W0612
    (unused_new_entity, deltas) = \
      modelutils.set_entity_attributes(user_interest,
                                 { models.USER_INTEREST_LIKED: new_value },
                                 None)

    if deltas is not None:  # Explicit check against None.
      success = models.VolunteerOpportunityStats.increment(opp_id, deltas)
      if success:
        self.response.out.write('ok')
        return

    self.error(500)  # Server error.


class static_content(webapp.RequestHandler):
  """Handles static content like privacy policy and 'About Us'

  The static content files are checked in SVN under /frontend/html.
  We want to be able to update these files without having to push the
  entire website.  The code here fetches the content directly from SVN,
  memcaches it, and serves that.  So once a static content file is
  submitted into SVN, it will go live on the site automatically (as soon
  as memcache entry expires) without requiring a full site push.
  """
  STATIC_CONTENT_MEMCACHE_TIME = 60 * 60  # One hour.
  STATIC_CONTENT_MEMCACHE_KEY = 'static_content:'

  @expires(0)  # User specific. Maybe we should remove that so it's cacheable.
  def get(self):
    """HTTP get method."""
    remote_url = (urls.STATIC_CONTENT_LOCATION +
        urls.STATIC_CONTENT_FILES[self.request.path])

    text = memcache.get(self.STATIC_CONTENT_MEMCACHE_KEY + remote_url)
    if not text:
      # Content is not in memcache.  Fetch from remote location.
      # We have to append ?zx= to URL to avoid urlfetch's cache.
      result = urlfetch.fetch("%s?zx=%d" % (remote_url,
                                            datetime.now().microsecond))
      if result.status_code == 200:
        text = result.content
        memcache.set(self.STATIC_CONTENT_MEMCACHE_KEY + remote_url,
                     text,
                     self.STATIC_CONTENT_MEMCACHE_TIME)

    if not text:
      self.error(404)
      return

    template_values = get_default_template_values(self.request, 'STATIC_PAGE')
    template_values['static_content'] = text
    self.response.out.write(render_template(STATIC_CONTENT_TEMPLATE,
                                            template_values))

class datahub_dashboard_view(webapp.RequestHandler):
  """stats by provider, on a hidden URL (underlying data is a hidden URL)."""
  @expires(0)
  def get(self):
    """shutup pylint"""
    template_values = {
      'msg': '',
      'action': '',
      'version' : os.getenv('CURRENT_VERSION_ID'),
    }
    url = self.request.get('datahub_log')
    if not url or url == "":
      url = DATAHUB_LOG
    fetch_result = urlfetch.fetch(url)
    if fetch_result.status_code != 200:
      template_values['msg'] = \
          "error fetching dashboard data: code %d" % fetch_result.status_code

    if re.search(r'[.]bz2$', url):
      import bz2
      fetch_result.content = bz2.decompress(fetch_result.content)
    lines = fetch_result.content.split("\n")
    # typical line
    # 2009-04-26 18:07:16.295996:STATUS:extraordinaries done parsing: output
    # 7 organizations and 7 opportunities (13202 bytes): 0 minutes.
    statusrx = re.compile("(\d+-\d+-\d+) (\d+:\d+:\d+)[.]\d+:STATUS:(.+?) "+
                          "done parsing: output (\d+) organizations and "+
                          "(\d+) opportunities .(\d+) bytes.: (\d+) minutes")
    def parse_date(datestr, timestr):
      """uses day granularity now that we have a few weeks of data.
      At N=10 providers, 5 values, 12 bytes each, 600B per record.
      daily is reasonable for a year, hourly is not."""
      #match = re.search(r'(\d+):', timestr)
      #hour = int(match.group(1))
      #return datestr + str(4*int(hour / 4)) + ":00"
      return datestr

    js_data = ""
    known_dates = {}
    date_strings = []
    known_providers = {}
    provider_names = []
    for line in lines:
      match = re.search(statusrx, line)
      if match:
        hour = parse_date(match.group(1), match.group(2))
        known_dates[hour] = 0
        known_providers[match.group(3)] = 0
        #js_data += "// hour="+hour+" provider="+match.group(3)+"\n"
    template_values['provider_data'] = provider_data = []
    sorted_providers = sorted(known_providers.keys())
    for i, provider in enumerate(sorted_providers):
      known_providers[provider] = i
      provider_data.append([])
      provider_names.append(provider)
      #js_data += "// provider_names["+str(i)+"]="+provider_names[i]+"\n"
    sorted_dates = sorted(known_dates.keys())
    for i, hour in enumerate(sorted_dates):
      for j, provider in enumerate(sorted_providers):
        provider_data[j].append({})
      known_dates[hour] = i
      date_strings.append(hour)
    #js_data += "// date_strings["+str(i)+"]="+date_strings[i]+"\n"
    def commas(num):
      num = str(num)
      while True:
        newnum, count = re.subn(r'(\d)(\d\d\d)(,|[.]|$)', r'\1,\2', num)
        if count == 0:
          break
        num = newnum
      return num
    max_date = {}
    for line in lines:
      match = re.search(statusrx, line)
      if match:
        hour = parse_date(match.group(1), match.group(2))
        date_idx = known_dates[hour]
        provider = match.group(3)
        provider_idx = known_providers[provider]
        max_date[provider_idx] = re.sub(r':\d\d$', '',
                                        match.group(1) + " " + match.group(2))
        rec = provider_data[provider_idx][date_idx]
        rec['organizations'] = int(match.group(4))
        rec['listings'] = int(match.group(5))
        rec['kbytes'] = int(float(match.group(6))/1024.0)
        rec['loadtimes'] = int(match.group(7))
    js_data += "function sv(row,col,val) {data.setValue(row,col,val);}\n"
    js_data += "function ac(typ,key) {data.addColumn(typ,key);}\n"
    js_data += "function acn(key) {data.addColumn('number',key);}\n"

    # provider names are implemented as chart labels, so they line up
    # with the charts-- otherwise it just doesn't work right.
    js_data += "data = new google.visualization.DataTable();\n"
    js_data += "data.addRows(1);"
    for provider_idx, provider in enumerate(sorted_providers):
      js_data += "\nacn('"+provider+"');"
      js_data += "sv(0,"+str(provider_idx)+",0);"
    js_data += "data.addRows(1);"
    js_data += "\nacn('totals');"
    js_data += "sv(0,"+str(len(sorted_providers))+",0);"
    js_data += "\n"
    js_data += "var chart = new google.visualization.ImageSparkLine("
    js_data += "  document.getElementById('provider_names'));\n"
    js_data += "chart.draw(data,{width:160,height:50,showAxisLines:false,"
    js_data += "  showValueLabels:false,labelPosition:'right'});\n"

    # provider last loaded times are implemented as chart labels, so
    # they line up with the charts-- otherwise it just doesn't work.
    js_data += "data = new google.visualization.DataTable();\n"
    js_data += "data.addRows(1);"
    maxdate = ""
    for provider_idx, provider in enumerate(sorted_providers):
      js_data += "\nacn('"+max_date[provider_idx]+"');"
      js_data += "sv(0,"+str(provider_idx)+",0);"
      if maxdate < max_date[provider_idx]:
        maxdate = max_date[provider_idx]
    js_data += "data.addRows(1);"
    js_data += "\nacn('"+maxdate+"');"
    js_data += "sv(0,"+str(len(sorted_providers))+",0);"
    js_data += "\n"
    js_data += "var chart = new google.visualization.ImageSparkLine("
    js_data += "  document.getElementById('lastloaded'));\n"
    js_data += "chart.draw(data,{width:150,height:50,showAxisLines:false,"
    js_data += "  showValueLabels:false,labelPosition:'right'});\n"

    totals = {}
    for key in ['organizations', 'listings', 'kbytes', 'loadtimes']:
      totals[key] = 0
      js_data += "data = new google.visualization.DataTable();\n"
      js_data += "data.addRows("+str(len(sorted_dates))+");\n"
      colnum = 0
      for provider_idx, provider in enumerate(sorted_providers):
        colstr = ""
        try:
          # print the current number next to the graph
          colstr = "\nacn('"+commas(str(provider_data[provider_idx][-1][key]))+"');"
          totals[key] += provider_data[provider_idx][-1][key]
        except:
          colstr = "\nacn('0');"
        for date_idx, hour in enumerate(sorted_dates):
          try:
            rec = provider_data[provider_idx][date_idx]
            val = "sv("+str(date_idx)+","+str(colnum)+","+str(rec[key])+");"
          except:
            val = ""
          colstr += val
        colnum += 1
        js_data += colstr
      js_data += "data.addRows(1);"
      js_data += "\nacn('"+commas(str(totals[key]))+"');"
      js_data += "sv(0,"+str(len(sorted_providers))+",0);"
      js_data += "\n"
      js_data += "var chart = new google.visualization.ImageSparkLine("
      js_data += "  document.getElementById('"+key+"_chart'));\n"
      js_data += "chart.draw(data,{width:200,height:50,showAxisLines:false,"
      js_data += "  showValueLabels:false,labelPosition:'right'});\n"
    template_values['datahub_dashboard_js_data'] = js_data
    logging.debug("datahub_dashboard_view: %s" % template_values['msg'])
    self.response.out.write(render_template(DATAHUB_DASHBOARD_TEMPLATE,
                                            template_values))

