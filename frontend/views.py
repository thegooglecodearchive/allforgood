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
import sys
import urllib
import logging
import re
import time
import codecs

import utf8
codecs.register_error('asciify', utf8.asciify)

from django.utils import simplejson

import private_keys
class CAMPAIGN_SPREADSHEET:
  KEY = '0Ak1XDmmFyJT2dC04N1JmYVJ0ME9nbjZYSWwwWTh5Umc'
  NAME = 'CS3 Campaigns'
  
class SHORT_NAME_SPREADSHEET:
  KEY = '0Ak1XDmmFyJT2dHRsMFVTd044Nkp5aVZJdVZzT2hrbkE'
  NAME = 'AFG.org Short to Long Names'

#from versioned_memcache import memcache
from google.appengine.api import memcache
from google.appengine.api import urlfetch
from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

from google.appengine.runtime import DeadlineExceededError

from third_party.recaptcha.client import captcha

import api
import solr_search
import geocode_mapsV3 as geocode
import models
import modelutils
import posting
import search
import urls
import userinfo
import utils
import view_helper
import searchresult
import apiwriter
from template_helpers import get_default_template_values, render_template, load_userinfo_into_dict
import ga

CONTENT_TEMPLATE = 'base_content.html'
HOME_PAGE_TEMPLATE = 'base_home.html'
PARTNER_PAGE_TEMPLATE = 'base_partners.html'
NOT_FOUND_TEMPLATE = 'not_found.html'

SEARCH_RESULTS_TEMPLATE = 'base_serp.html'

TEST_PAGEVIEWS_TEMPLATE = 'test_pageviews.html'
SEARCH_RESULTS_MISSING_KEY_TEMPLATE = 'search_results_missing_key.html'
SNIPPETS_LIST_TEMPLATE = 'serp_results.html'
SNIPPETS_LIST_MINI_TEMPLATE = 'snippets_list_home.html'
POST_TEMPLATE = 'post.html'
POST_RESULT_TEMPLATE = 'post_result.html'
ADMIN_TEMPLATE = 'admin.html'
DATAHUB_DASHBOARD_TEMPLATE = 'datahub_dashboard.html'
MODERATE_TEMPLATE = 'moderate.html'

MY_EVENTS_TEMPLATE = 'my_events.html'

DATAHUB_LOG = private_keys.DASHBOARD_BASE_URL + "load_gbase.log.bz2"

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
    value = allvals[len(allvals)-1]

    value = urllib.unquote(value)
    try:
      value = value.encode('ascii', 'asciify')
    except:
      # encode as ascii and drop errors, same as pipeline 
      value = value.encode('ascii', 'ignore')

    unique_args[arg] = value

  return unique_args


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
      logging.warning('views.require_moderator non-moderator blacklist attempt')
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
      logging.warning('views.require_usig XSRF attempt %s!=%s',
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
      else:
        self.response.headers['Cache-Control'] = 'public'
        self.response.headers['Expires'] = email.Utils.formatdate(
            time.time() + seconds, usegmt=True)
      # The handler method can now re-write these if needed.
      return handler_method(self)
    return decorate
  return decorator

def deadline_exceeded(request_handler, fx_name):
  """ DeadlineExceeded handler """
  # http://code.google.com/appengine/docs/python/runtime.html
  # now that we are here, we have about one second to live
  #
  # the reason for trapping this error is that otherwise it puts 
  # a traceback in the log which is great for detailed debugging but 
  # makes it hard to see the patterns, ie most freq. causes
  #
  # if we wanted to retry the request we could do this...
  # request_handler.redirect(urls.URL_CONSUMER_UI_SEARCH + "#" +
  #                          request_handler.request.query_string)
  # but then an evil request could loop us to infinity and beyond 
  #
  # maybe an 'oops' page  would be nicer, esp for the API
  # for which we could ouput <error>timeout</error> 
  # but for now...
  request_handler.response.set_status(500)
  request_handler.response.out.write("request timed out")
  logging.error('views.%s exceeded deadline' % fx_name)


class home_page_view(webapp.RequestHandler):
  """ default homepage for consumer UI."""
  @expires(0)  # User specific. Maybe we should remove that so it's cacheable.
  def get(self):
    """HTTP get method."""
    try:
      try:
        path = os.path.join(os.path.dirname(__file__),  urls.CONTENT_LOCATION +
                        urls.CONTENT_FILES[self.request.path])
        fh = open(path, 'r')
        html = fh.read()
        fh.close()
        template_values = get_default_template_values(self.request, 'HOME_PAGE')
        template_values['static_content'] = html
        self.response.out.write(render_template(HOME_PAGE_TEMPLATE,
                                          template_values))
      except:
        logging.warning('home_page_view: ' + path)
        self.error(404)
        return

    except DeadlineExceededError:
      deadline_exceeded(self, "static_content")


class partner_page_view(webapp.RequestHandler):
  """ default homepage for consumer UI."""
  @expires(0)  # User specific. Maybe we should remove that so it's cacheable.
  def get(self):
    """HTTP get method."""
    try:
      try:
        path = os.path.join(os.path.dirname(__file__),  urls.CONTENT_LOCATION +
                        urls.CONTENT_FILES[self.request.path])
        fh = open(path, 'r')
        html = fh.read()
        fh.close()
        template_values = get_default_template_values(self.request, 'PARTNER_PAGE')
        template_values['static_content'] = html
        self.response.out.write(render_template(PARTNER_PAGE_TEMPLATE,
                                          template_values))
      except:
        logging.warning('partner_page_view: ' + path)
        self.error(404)
        return

    except DeadlineExceededError:
      deadline_exceeded(self, "static_content")



class home_page_redir_view(webapp.RequestHandler):
  """handler for /home, which somehow got indexed by google."""
  @expires(0)
  def get(self):
    """HTTP get method."""
    self.redirect("/")


class home4holidays_redir_view(webapp.RequestHandler):
  """handler for /home4holidays """
  @expires(0)
  def get(self):
    """HTTP get method."""
    self.redirect("http://www.gmodules.com/ig/creator?url=http%3A%2F%2Fhosting.gmodules.com%2Fig%2Fgadgets%2Ffile%2F110804810900731027561%2Fiams.xml")


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
    try:
      dest = urls.URL_CONSUMER_UI_SEARCH + "#" + self.request.query_string
      self.redirect(dest)
    except DeadlineExceededError:
      deadline_exceeded(self, "consumer_ui_search_redir_view")


class consumer_ui_search_view(webapp.RequestHandler):
  """default homepage for consumer UI."""
  @expires(0)  # User specific.
  def get(self):
    """HTTP get method."""
    try:
      template_values = get_default_template_values(self.request, 'SEARCH')
      template_values['result_set'] = {}
      template_values['template'] = 'serp.html'
      template_values['is_main_page'] = True
      template_values['private_keys'] = private_keys

      template_values['is_report'] = False
      if self.request.url.find('/report') >= 0:
        template_values['is_report'] = True

      self.response.out.write(render_template(SEARCH_RESULTS_TEMPLATE,
                                           template_values))
    except DeadlineExceededError:
      deadline_exceeded(self, "static_content")


class search_view(webapp.RequestHandler):
  """run a search from the API.  note various output formats."""
  #@expires(1800)  # Search results change slowly; cache for half an hour.

  def post(self):
    """HTTP post method."""
    return self.get()

  def get(self):
    """HTTP get method."""
    try:
      unique_args = get_unique_args_from_request(self.request)

      if api.PARAM_KEY not in unique_args or unique_args[api.PARAM_KEY] in private_keys.BAD_KEYS:
        if api.PARAM_KEY not in unique_args:
          logging.info('no key given')
        elif unique_args[api.PARAM_KEY] in private_keys.BAD_KEYS:
          logging.info('bad key given %s' % private_keys.BAD_KEYS)

        tplresult = render_template(SEARCH_RESULTS_MISSING_KEY_TEMPLATE, {})
        self.response.out.write(tplresult)
        return

      ga.track("API", "search", unique_args[api.PARAM_KEY])

      dumping = False
      if api.PARAM_DUMP in unique_args and unique_args[api.PARAM_DUMP] == '1':
        dumping = True
        logging.info("dumping request");

      result_set = search.search(unique_args, dumping)
  
      # insert the interest data-- API searches are anonymous, so set the user
      # interests to 'None'.  Note: left here to avoid polluting searchresults.py
      # with view_helper.py and social/personalization stuff.
      opp_ids = []
      # perf: only get interest counts for opps actually in the clipped results
      for primary_res in result_set.clipped_results:
        opp_ids += [result.item_id for result in primary_res.merged_list]

      if not dumping:
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
      
      if not output:
        output = "html"

      if output == "html":
        if "geocode_responses" not in unique_args:
          unique_args["geocode_responses"] = 1
    
      latlng_string = ""
      if api.PARAM_LAT in result_set.args and api.PARAM_LNG in result_set.args:
        latlng_string = "%s,%s" % (result_set.args[api.PARAM_LAT],
                                 result_set.args[api.PARAM_LNG])
        result_set.args["latlong"] = latlng_string
      logging.debug("geocode("+result_set.args[api.PARAM_VOL_LOC]+") = "+
                  result_set.args[api.PARAM_LAT]+","+result_set.args[api.PARAM_LNG])

      result_set.is_hoc = True if output.find('hoc') >= 0 else False
      result_set.is_rss = True if output.find('rss') >= 0 else False
      result_set.is_cal = True if output.find('cal') >= 0 else False
      result_set.is_json2 = True if output.find('json-2') >= 0 else False
      result_set.is_exelis = True if output.find('exelis') >= 0 else False

      if (result_set.is_hoc or result_set.is_rss):
        result_set = solr_search.apply_HOC_facet_counts(result_set, unique_args)

      writer = apiwriter.get_writer(output)
      writer.setup(self.request, result_set)
      logging.info('views.search_view clipped %d, beginning apiwriter' % 
                  len(result_set.clipped_results))

      for result in result_set.clipped_results:
        writer.add_result(result, result_set)

      logging.info('views.search_view completed apiwriter')

      self.response.headers["Content-Type"] = writer.content_type
      self.response.out.write(writer.finalize())
      logging.info('views.search_view completed %d' % 
                  len(result_set.clipped_results))
    except DeadlineExceededError:
      deadline_exceeded(self, "search_view")


class ui_snippets_view(webapp.RequestHandler):
  """run a search and return consumer HTML for the results """
  @expires(0) 
  def get(self):
    """HTTP get method."""
    try:
      campaign_id = self.request.get('campaign_id', None)
      unique_args = get_unique_args_from_request(self.request)
      if api.PARAM_REFERRER in unique_args and len(unique_args[api.PARAM_REFERRER]) > 0:
        logging.info('referred by %s' % unique_args[api.PARAM_REFERRER])
        if api.PARAM_KEY not in unique_args or len(unique_args[api.PARAM_KEY]) < 1:
          for kf in private_keys.KEYED_REFERRERS:
            if unique_args[api.PARAM_REFERRER].lower().find(kf['id']) >= 0:
              unique_args[api.PARAM_KEY] = kf['key']

      unique_args['is_report'] = False
      for line in str(self.request).split('\n'):
        if line.find('Referer:') >= 0 and line.find('/report') >= 0:
          unique_args['is_report'] = True
          break

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

      virtual = unique_args.get(api.PARAM_VIRTUAL, False)
      if virtual:
        template_values['query_param_virtual'] = True

      hp_num = min(3, len(result_set.clipped_results))
      template_values.update({
          'result_set': result_set,
          'has_results' : (result_set.num_merged_results > 0),  # For django.
          'last_result_index' : result_set.estimated_results,
          'display_nextpage_link' : result_set.has_more_results,
          'friends' : view_data['friends'],
          'friends_by_event_id_js': view_data['friends_by_event_id_js'],
          'query_param_q' : unique_args.get(api.PARAM_Q, None),
          'full_list' : self.request.get('minimal_snippets_list') != '1',
          'six_results' : result_set.clipped_results[:hp_num],
        })

      if self.request.get('minimal_snippets_list'):
        # Minimal results list for homepage.
        result_set.clipped_results.sort(cmp=searchresult.compare_result_dates)
        self.response.out.write(render_template(SNIPPETS_LIST_MINI_TEMPLATE,
                                              template_values))
      else:
        self.response.out.write(render_template(SNIPPETS_LIST_TEMPLATE,
                                                template_values))
    except DeadlineExceededError:
      deadline_exceeded(self, "ui_snippets_view")


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
    for arg, argv in get_unique_args_from_request(self.request).items():
      geturl += urllib.quote_plus(arg) + "=" + urllib.quote_plus(argv) + "&"
    template_values = {
      'current_page' : 'POST',
      'geturl' : geturl,
      'version' : os.getenv('CURRENT_VERSION_ID'),
      'private_keys': private_keys,
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
      for arg, argv in get_unique_args_from_request(self.request).items():
        vals[arg] = argv
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
        self.response.out.write("internal viewserror: duplicate template key")
        logging.error('views.post_view duplicate template key: %s' % keystr)
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
      'private_keys': private_keys,
    }

    # Get memcache stats and calculate some useful percentages
    memcache_stats = memcache.get_stats()
    try:
      hits = memcache_stats['hits']
      misses = memcache_stats['misses']
      memcache_stats['hit_percent'] = '%4.1f%%' % ((100.0 * hits) / (hits + misses))
    except ZeroDivisionError:
      # Don't think we'll ever hit this but just in case...
      memcache_stats['hit_percent'] = 100.0
    memcache_stats['size'] = memcache_stats['bytes'] / (1024*1024)
    memcache_stats['size_unit'] = 'MB'
    if memcache_stats['size'] < 1:
      memcache_stats['size'] = memcache_stats['bytes'] / 1024
      memcache_stats['size_unit'] = 'KB'
    template_values['memcache_stats'] = memcache_stats

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
      logging.warning('views.admin.post XSRF attempt. %s!=%s', 
              usig, self.request.get('usig'))
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
      # this is 301, permanent
      self.redirect(url, permanent=True)

      # this is 302 temporary
      #self.redirect(url)
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
        vals = get_unique_args_from_request(self.request)
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
    self.response.out.write(render_template(urls.CONTENT_TEMPLATE,
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
    self.response.out.write(render_template(CONTENT_TEMPLATE,
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
      logging.warning('views.action_view No user.')
      self.error(401)  # Unauthorized
      return

    if not opp_id or not base_url or not new_value:
      logging.warning('views.action_view bad param')
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
      logging.warning('views.action_view Attempted XSRF.')
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
  """Handles static content like privacy policy and 'About Us'"""
  @expires(0)  # User specific. Maybe we should remove that so it's cacheable.
  def get(self):
    """HTTP get method."""
    try:
      try:
        path = os.path.join(os.path.dirname(__file__), urls.CONTENT_LOCATION +
                        urls.CONTENT_FILES[self.request.path])
        fh = open(path, 'r')
        html = fh.read()
        fh.close()
        template_values = get_default_template_values(self.request, 'STATIC_PAGE')
        template_values['static_content'] = html
        self.response.out.write(render_template(CONTENT_TEMPLATE,
                                          template_values))
      except:
        logging.warning('static_content: ' + path)
        self.error(404)
        return

    except DeadlineExceededError:
      deadline_exceeded(self, "static_content")


class not_found_handler(webapp.RequestHandler):
  """ throw 404 """
  @expires(0)  # User specific. Maybe we should remove that so it's cacheable.
  def get(self):
    """HTTP get method."""
    try:
      self.error(404)
      template_values = get_default_template_values(self.request, 'STATIC_PAGE')
      template_values['template'] = NOT_FOUND_TEMPLATE
      self.response.out.write(render_template(CONTENT_TEMPLATE,
                                          template_values))

    except DeadlineExceededError:
      deadline_exceeded(self, "not_found_handler")


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

    unique_args = get_unique_args_from_request(self.request)
    detail_idx = None
    show_details = False
    if 'provider_idx' in unique_args:
      try:
        detail_idx = int(unique_args['provider_idx'])
        show_details = True
      except:
        pass

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
    details_html = ""

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
    js_data += "provider_chart = new google.visualization.ImageSparkLine("
    js_data += "  document.getElementById('provider_names'));\n"
    js_data += "provider_chart.draw(data,{width:160,height:50,showAxisLines:false,"
    js_data += "  showValueLabels:false,labelPosition:'left'});\n"

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
    js_data += "  showValueLabels:false,labelPosition:'left'});\n"

    history_details = []
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

        dated_values = []
        for date_idx, hour in enumerate(sorted_dates):
          try:
            rec = provider_data[provider_idx][date_idx]
            val = "sv("+str(date_idx)+","+str(colnum)+","+str(rec[key])+");"
            dated_values.append({'date':hour, key:str(rec[key])})
          except:
            val = ""
          colstr += val
        colnum += 1
        js_data += colstr

        if key == 'listings':
          while len(history_details) <= provider_idx:
            history_details.append({'date':'-',key:'0'})
          history_details[provider_idx] = dated_values

      if show_details and len(details_html) < 1:
        for provider_idx, provider in enumerate(sorted_providers):
          if provider_idx < len(history_details) and provider_idx == detail_idx:
            details_html += ('<div class="details"><h3><a id="anchor' + str(detail_idx) + 
                        '" name="anchor' + str(detail_idx) + 
                        '">' + provider + '</a></h3>\n')
            details_html += '<table>\n'
            for rec in history_details[provider_idx]:
              details_html += "<tr><td>%s</td><td>%s</td></tr>\n" % (rec['date'], rec['listings'])
            details_html += '</table></div>\n'
            break

      js_data += "data.addRows(1);"
      js_data += "\nacn('"+commas(str(totals[key]))+"');"
      js_data += "sv(0,"+str(len(sorted_providers))+",0);"
      js_data += "\n"
      js_data += "var chart = new google.visualization.ImageSparkLine("
      js_data += "  document.getElementById('"+key+"_chart'));\n"
      js_data += "chart.draw(data,{width:200,height:50,showAxisLines:false,"
      js_data += "  showValueLabels:false,labelPosition:'right'});\n"

    template_values['datahub_dashboard_js_data'] = js_data
    template_values['datahub_dashboard_history'] = details_html

    logging.debug("datahub_dashboard_view: %s" % template_values['msg'])
    self.response.out.write(render_template(DATAHUB_DASHBOARD_TEMPLATE,
                                            template_values))


class short_name_view(webapp.RequestHandler):
  """Redirects short name to long URL from spreadsheet."""
  @expires(0)
  def get(self):
    """Redirect to long url, or 404 if not found in spreadsheet."""
    import gdata
    import gdata.service
    import gdata.spreadsheet
    import gdata.spreadsheet.service
    import gdata.alt
    import gdata.alt.appengine
    query = gdata.spreadsheet.service.DocumentQuery()
    # We use the structured query option to get back a minimal
    # result set.  This is preferable to getting the whole sheet
    # and parsing on our end.
    # NOTE: GData API strips whitespace (including underscores) from
    # column names.  So the column 'campaign_id' is actually 'campaignid'
    # when using the GData API.
    short_name = self.request.path.split('/')[-1]
    # NOTE: I get back an error if the short name includes dashes (-)
    # in it.  I think I need to escape them but the GData docs are unclear
    # as to the escape format.
    query['sq'] = 'short==%s' % (short_name)
    gd_client = gdata.spreadsheet.service.SpreadsheetsService()
    gdata.alt.appengine.run_on_appengine(gd_client, store_tokens=False,
                                         single_user_mode=True)
    gd_client.email = private_keys.AFG_GOOGLE_DOCS_LOGIN['username']
    gd_client.password = private_keys.AFG_GOOGLE_DOCS_LOGIN['password']
    gd_client.source = SHORT_NAME_SPREADSHEET.NAME
    gd_client.ProgrammaticLogin()
    rows = gd_client.GetListFeed(
      key= SHORT_NAME_SPREADSHEET.KEY,
      # wksht_id is the 1s based index of which sheet to use
      wksht_id = '1',
      query = query )
    # make sure we get some results
    if rows and len(rows.entry):
      row = rows.entry[0]
      long_url = row.custom['long'].text
      if not long_url.startswith('/'):
        long_url = '/' + long_url
        self.redirect(long_url)
        return
    self.error(404)
      
    
  
