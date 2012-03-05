#!/usr/bin/env python

import os

# Must set this env var before importing any part of Django
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

from google.appengine.dist import use_library
use_library('django', '1.2')

from django.template.defaultfilters import register
from django.utils import simplejson as json
from functools import wraps
from google.appengine.api import urlfetch, taskqueue
from google.appengine.ext import db, webapp
from google.appengine.ext.webapp import util, template
from google.appengine.runtime import DeadlineExceededError
from random import randrange
from uuid import uuid4
import Cookie
import base64
import cgi
import datetime
import hashlib
import hmac
import logging
import time
import traceback
import urllib

import fb.conf as conf

def htmlescape(text):
    """Escape text for use as HTML"""
    return cgi.escape(
        text, True).replace("'", '&#39;').encode('ascii', 'xmlcharrefreplace')


@register.filter(name='get_name')
def get_name(dic, index):
    """Django template filter to render name"""
    return dic[index].name


@register.filter(name='get_picture')
def get_picture(dic, index):
    """Django template filter to render picture"""
    return dic[index].picture


_USER_FIELDS = 'name,picture,gender,locale,link,username'
class User(db.Model):
    user_id = db.StringProperty()
    access_token = db.StringProperty()
    name = db.StringProperty()
    picture = db.StringProperty()
    gender = db.StringProperty()
    locale = db.StringProperty()
    link = db.StringProperty()
    dirty = db.BooleanProperty()

    def refresh_data(self):
        """Refresh this user's data using the Facebook Graph API"""
        me = Facebook().api('/me',
            {'fields': _USER_FIELDS, 'access_token': self.access_token})
        self.dirty = False
        self.name = me['name']
        self.picture = me['picture']
        self.gender = me['gender']
        self.locale = me['locale']
        self.link = me['link']
        return self.put()


class Exception(Exception):
    pass


class FacebookApiError(Exception):
    def __init__(self, result):
        self.result = result

    def __str__(self):
        return self.__class__.__name__ + ': ' + json.dumps(self.result)


class Facebook(object):
    """Wraps the Facebook specific logic"""
    def __init__(self, app_id=conf.FACEBOOK_APP_ID,
            app_secret=conf.FACEBOOK_APP_SECRET):
        self.app_id = app_id
        self.app_secret = app_secret
        self.user_id = None
        self.access_token = None
        self.signed_request = {}

    def api(self, path, params=None, method='GET', domain='graph'):
        """Make API calls"""
        if not params:
            params = {}
        params['method'] = method
        if 'access_token' not in params and self.access_token:
            params['access_token'] = self.access_token
        result = json.loads(urlfetch.fetch(
            url='https://' + domain + '.facebook.com' + path,
            payload=urllib.urlencode(params),
            method=urlfetch.POST,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded'})
            .content)
        if isinstance(result, dict) and 'error' in result:
            raise FacebookApiError(result)
        return result

    def load_signed_request(self, signed_request):
        """Load the user state from a signed_request value"""
        try:
            sig, payload = signed_request.split('.', 1)
            sig = self.base64_url_decode(sig)
            data = json.loads(self.base64_url_decode(payload))

            expected_sig = hmac.new(
                self.app_secret, msg=payload, digestmod=hashlib.sha256).digest()

            # allow the signed_request to function for upto 1 day
            if sig == expected_sig and \
                    data['issued_at'] > (time.time() - 86400):
                self.signed_request = data
                self.user_id = data.get('user_id')
                self.access_token = data.get('oauth_token')
        except ValueError, ex:
            pass # ignore if can't split on dot

    @property
    def user_cookie(self):
        """Generate a signed_request value based on current state"""
        if not self.user_id:
            return
        payload = self.base64_url_encode(json.dumps({
            'user_id': self.user_id,
            'issued_at': str(int(time.time())),
        }))
        sig = self.base64_url_encode(hmac.new(
            self.app_secret, msg=payload, digestmod=hashlib.sha256).digest())
        return sig + '.' + payload

    @staticmethod
    def base64_url_decode(data):
        data = data.encode('ascii')
        data += '=' * (4 - (len(data) % 4))
        return base64.urlsafe_b64decode(data)

    @staticmethod
    def base64_url_encode(data):
        return base64.urlsafe_b64encode(data).rstrip('=')


class CsrfException(Exception):
    pass


class BaseHandler(webapp.RequestHandler):
    facebook = None
    user = None
    csrf_protect = True

    def initialize(self, request, response):
        """General initialization for every request"""
        super(BaseHandler, self).initialize(request, response)

        try:
            self.init_facebook()
            self.init_csrf()
            self.response.headers['P3P'] = 'CP=HONK'  # iframe cookies in IE
        except Exception, ex:
            #self.log_exception(ex)
            #raise
            pass

    def handle_exception(self, ex, debug_mode):
        """Invoked for unhandled exceptions by webapp"""
        self.log_exception(ex)
        self.render('error',
            trace=traceback.format_exc(), debug_mode=debug_mode)

    def log_exception(self, ex):
        """Internal logging handler to reduce some App Engine noise in errors"""
        msg = ((str(ex) or ex.__class__.__name__) +
                ': \n' + traceback.format_exc())
        if isinstance(ex, urlfetch.DownloadError) or \
           isinstance(ex, DeadlineExceededError) or \
           isinstance(ex, CsrfException) or \
           isinstance(ex, taskqueue.TransientError):
            logging.warn(msg)
        else:
            logging.error(msg)

    def set_cookie(self, name, value, expires=None):
        """Set a cookie"""
        if value is None:
            value = 'deleted'
            expires = datetime.timedelta(minutes=-50000)
        jar = Cookie.SimpleCookie()
        jar[name] = value
        jar[name]['path'] = '/'
        if expires:
            if isinstance(expires, datetime.timedelta):
                expires = datetime.datetime.now() + expires
            if isinstance(expires, datetime.datetime):
                expires = expires.strftime('%a, %d %b %Y %H:%M:%S')
            jar[name]['expires'] = expires
        self.response.headers.add_header(*jar.output().split(': ', 1))

    def render(self, name, **data):
        """Render a template"""
        if not data:
            data = {}
        data['js_conf'] = json.dumps({
            'appId': conf.FACEBOOK_APP_ID,
            'canvasName': conf.FACEBOOK_CANVAS_NAME,
            'userIdOnServer': self.user.user_id if self.user else None,
        })
        data['logged_in_user'] = self.user
        data['message'] = self.get_message()
        data['csrf_token'] = self.csrf_token
        data['canvas_name'] = conf.FACEBOOK_CANVAS_NAME
        self.response.out.write(template.render(
            os.path.join(
                os.path.dirname(__file__), 'templates', name + '.html'),
            data))

    def init_facebook(self):
        """Sets up the request specific Facebook and User instance"""
        facebook = Facebook()
        user = None
        me = None

        # initial facebook request comes in as a POST with a signed_request
        if 'signed_request' in self.request.POST:
            facebook.load_signed_request(self.request.get('signed_request'))
            # we reset the method to GET because a request from facebook with a
            # signed_request uses POST for security reasons, despite it
            # actually being a GET. in webapp causes loss of request.POST data.
            self.request.method = 'GET'
            self.set_cookie(
                '', facebook.user_cookie, datetime.timedelta(minutes=1440))
        elif '' in self.request.cookies:
            facebook.load_signed_request(self.request.cookies.get(''))

        # try to load or create a user object
        if facebook.user_id:
            user = User.get_by_key_name(facebook.user_id)
            if user:
                # update stored access_token
                if facebook.access_token and \
                        facebook.access_token != user.access_token:
                    user.access_token = facebook.access_token
                    user.put()
                # refresh data if we failed in doing so after a realtime ping
                if user.dirty:
                    user.refresh_data()
                # restore stored access_token if necessary
                if not facebook.access_token:
                    facebook.access_token = user.access_token

                me = facebook.api('/me', {'fields': _USER_FIELDS})

            if not user and facebook.access_token:
                me = facebook.api('/me', {'fields': _USER_FIELDS})
                try:
                    user = User(key_name=facebook.user_id,
                        user_id=facebook.user_id, 
                        access_token=facebook.access_token, 
                        name=me['name'],
                        picture=me['picture'],
                        gender=me['gender'],
                        locale=me['locale'],
                        link=me['link'],
                        username=me['username'],
                       )
                    user.put()
                except KeyError, ex:
                    pass # ignore if can't get the minimum fields

        if me:
          logging.info(str(me))

        self.facebook = facebook
        self.user = user

    def init_csrf(self):
        """Issue and handle CSRF token as necessary"""
        self.csrf_token = self.request.cookies.get('c')
        if not self.csrf_token:
            self.csrf_token = str(uuid4())[:8]
            self.set_cookie('c', self.csrf_token)
        if self.request.method == 'POST' and self.csrf_protect and \
                self.csrf_token != self.request.POST.get('_csrf_token'):
            raise CsrfException('Missing or invalid CSRF token.')

    def set_message(self, **obj):
        """Simple message support"""
        self.set_cookie('m', base64.b64encode(json.dumps(obj)) if obj else None)

    def get_message(self):
        """Get and clear the current message"""
        message = self.request.cookies.get('m')
        if message:
            self.set_message()  # clear the current cookie
            return json.loads(base64.b64decode(message))


def user_required(fn):
    """Decorator to ensure a user is present"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        handler = args[0]
        if handler.user:
            return fn(*args, **kwargs)
        handler.redirect('/')
    return wrapper


class RequestHandler(BaseHandler):
    """  """
    def post(self):
      get(self)

    def get(self):
      if not self.user:
        # only do this if we have to ask for privs
        #self.render('welcome')
        self.render('main')
      else:
        self.render('main')


def main():
    routes = [
        (r'/fb.*', RequestHandler),
    ]
    is_local = os.environ.get('SERVER_SOFTWARE', '').startswith('Dev')
    application = webapp.WSGIApplication(routes, debug=is_local)
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()
