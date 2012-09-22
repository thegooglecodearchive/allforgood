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

# Various test pages.

# view classes aren inherently not pylint-compatible
# pylint: disable-msg=C0103
# pylint: disable-msg=W0232
# pylint: disable-msg=E1101
# pylint: disable-msg=R0903

import cgi
import datetime
import re

from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

import models
import userinfo
import utils

# require_admin is copied from views.py so we don't have to import all of it.
def require_admin(handler_method):
  """Decorator ensuring the current App Engine user is an administrator."""
  def Decorate(self):
    if not users.is_current_user_admin():
      self.error(401)
      html = '<html><body><a href="%s">Sign in</a></body></html>'
      self.response.out.write(html % (users.create_login_url(self.request.url)))
      return
    return handler_method(self)
  return Decorate

class TestLogin(webapp.RequestHandler):
  """test user login sequence."""
  # This is still useful for testing but we'll limit it to just admins.
  @require_admin  
  def get(self):
    """HTTP get method."""
    user = userinfo.get_user(self.request)
    self.response.out.write('Login info<ul>')
    if user:
      self.response.out.write('<li>Account type: %s'
                              '<li>User_id: %s'
                              '<li>User_info:  %s'
                              '<li>Name: %s'
                              '<li>Moderator: %s'
                              '<li>Image: %s <img src="%s" />' %
                              (user.account_type,
                               user.user_id,
                               user.get_user_info(),
                               user.display_name,
                               user.get_user_info().moderator,
                               user.thumbnail_url,
                               user.thumbnail_url))
    else:
      self.response.out.write('<li>Not logged in.')

    self.response.out.write('<li>Total # of users: %s' %
                            models.UserStats.get_count())

    self.response.out.write('</ul>')
    self.response.out.write('<form method="POST">'
                            'Userid: <input name="userid" />'
                            '<input name="Test Login" type="submit" />'
                            '(Blank form = logout)'
                            '</form>')
                            
  USERID_REGEX = re.compile('[a-z0-9_@+.-]*$')
                            
  @require_admin  
  def post(self):
    """HTTP post method."""
    try:
      userid = utils.get_verified_arg(self.USERID_REGEX, self.request, 
                                      'userid')
    except utils.InvalidValue:
      self.error(400)
      self.response.out.write('invalid userid, must be ^%s' %
                              self.USERID_REGEX.pattern)
      return

    self.response.headers.add_header('Set-Cookie',
                                     'footprinttest=%s;path=/' % userid)
    self.response.out.write('You are logged ')
    if userid:
      self.response.out.write('in!')
    else:
      self.response.out.write('out!')
    self.response.out.write('<br><a href="%s">Continue</a>' % self.request.url)


class TestModerator(webapp.RequestHandler):
  """test moderation functionality."""
  def get(self):
    """HTTP get method."""
    user = userinfo.get_user(self.request)
    if not user:
      self.response.out.write('Not logged in.')
      return

    self.response.out.write('Moderator Request<ul>')

    if user.get_user_info().moderator:
      self.response.out.write('<li>You are already a moderator.')

    if user.get_user_info().moderator_request_email:
      # TODO: This is very vulnerable to html injection.
      self.response.out.write('<li>We have received your request'
          '<li>Your email: %s'
          '<li>Your comments: %s' %
          (cgi.escape(user.get_user_info().moderator_request_email),
           cgi.escape(user.get_user_info().moderator_request_desc)))

    self.response.out.write('</ul>')
    self.response.out.write(
      '<form method="POST">'
      'Your email address: <input name="email" /><br>'
      'Why you want to be a moderator: <br><textarea name="desc"></textarea>'
      '<br><input type="submit" name="submit"/>'
      '</form>')

  def post(self):
    """HTTP post method."""
    # todo: xsrf protection
    user = userinfo.get_user(self.request)
    if not user:
      self.response.out.write('Not logged in.')
      return

    try:
      # This regex is a bit sloppy but good enough.
      email = utils.get_verified_arg(re.compile('[a-z0-9_+.-]+@[a-z0-9.-]+$'),
                                     self.request, 'email')
      desc = self.request.get('desc')
    except utils.InvalidValue:
      self.error(400)
      self.response.out.write('<div style="color:red">' +
                              'Valid email address required.</div>')
      return           

    user_info = user.get_user_info()
    user_info.moderator_request_email = self.request.get('email')
    user_info.moderator_request_desc = self.request.get('desc')
    if not user_info.moderator_request_admin_notes:
      user_info.moderator_request_admin_notes = ''
    user_info.moderator_request_admin_notes += (
        '%s: Requested.\n' %
        datetime.datetime.isoformat(datetime.datetime.now()))
    user_info.put()

    return self.get()


APP = webapp.WSGIApplication([
    ('/test/login', TestLogin),
    ('/test/moderator', TestModerator),
    ], debug=True)

def main():
  """main() for standalone execution."""
  run_wsgi_app(APP)

if __name__ == '__main__':
  main()
