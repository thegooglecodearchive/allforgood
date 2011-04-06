"""
<title>AJAX Proxy</title>
<pre>
Required: &url=[fully qualified url...]
Optional: &cache=[seconds...]

========================= Example ==================================================
/proxy?url=http://twitter.com/statuses/user_timeline/193774020.rss<xmp>
<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:atom="http://www.w3.org/2005/Atom" version="2.0" 
  xmlns:georss="http://www.georss.org/georss" xmlns:twitter="http://api.twitter.com">
  <channel>
    <title>Twitter / All_for_Good</title>
    <link>http://twitter.com/All_for_Good</link>
    <atom:link type="application/rss+xml" 
        href="http://twitter.com/statuses/user_timeline/34344129.rss" rel="self"/>
    <description>Twitter updates from All For Good / All_for_Good.</description>
    <language>en-us</language>
    <ttl>40</ttl>
  <item>
    <title>All_for_Good: Innovation in philanthropy is not new. What is new is its scale, propelled by the twin resources of money and... http://fb.me/xW0zmbeo</title>
    <description>All_for_Good: Innovation in philanthropy is not new. What is new is its scale, propelled by the twin resources of money and... http://fb.me/xW0zmbeo</description>
    <pubDate>Sun, 27 Mar 2011 01:45:08 +0000</pubDate>
    <guid>http://twitter.com/All_for_Good/statuses/51822024997343232</guid>
    <link>http://twitter.com/All_for_Good/statuses/51822024997343232</link>
    <twitter:source>&lt;a href=&quot;http://www.facebook.com/twitter&quot; rel=&quot;nofollow&quot;&gt;Facebook&lt;/a&gt;</twitter:source>
    <twitter:place/>
  </item>
  </channel>
</rss>
</xmp>
</pre>
"""

import os
import sys
import locale
import hashlib
import urllib
import logging

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import urlfetch
from google.appengine.api import memcache

PATH = "/proxy"
MAX_CACHE_LIFE = 15 * 60

def get_args(request):
  """ get arguments that came w/ this request """
  unique_args = {}
  for arg in request.arguments():
    allvals = request.get_all(arg)
    unique_args[arg] = allvals[len(allvals)-1]
  return unique_args


def get_memcache_key(query):
  """ make a key for memcache """
  # we use v=### in the key in case we ever need to reset all items
  return "%s/%s/v=003" % (PATH, hashlib.md5(query).hexdigest())


def GoFetch(url, cache_life):
  """ call the API we were created for """

  rtn = None
  if cache_life > 0:
    mkey = get_memcache_key(url)
    rtn = memcache.get(mkey)

  if rtn:
    logging.info("%s found in memcache %s" % (PATH, url))
  else:
    logging.info("%s fetching %s" % (PATH, url))
    try:
      purl = "http://afg.echo3.net/twitter/?url=" + urllib.quote(url)
      rsp = urlfetch.fetch(purl, headers={'User-Agent' : 'Google App Engine'})
      rtn = str(rsp.content)
    except:
      logging.warning("%s fetching %s failed" % (PATH, url))

    if rtn:
      if cache_life > 0:
        if not memcache.set(mkey, rtn):
          logging.warning("%s memcaching %s failed at %s" % (PATH, url, mkey))
        else:
          logging.info("%s set in cache %s for %s" % (PATH, url, cache_life))

  return rtn


class handleRequest(webapp.RequestHandler):
  """ handle request """
  def __init__(self):
    """ pylint wants a public init method """
    if hasattr(webapp.RequestHandler, '__init__'):
      webapp.RequestHandler.__init__(self)

  def request(self):
    """ pylint wants a public request method """
    webapp.RequestHandler.__request__(self)

  def response(self):
    """ pylint wants a public reponse method """
    webapp.RequestHandler.__response__(self)

  def get(self):
    """ get results from datastore or API """
    args = get_args(self.request)

    url = None
    if 'url' in args:
      url = args['url']

    cache_life = MAX_CACHE_LIFE
    if 'cache' in args:
      try:
        cache_life = int(args['cache'])
      except:
        pass

    if not url:
      # no arguments so hand this whole request off to ShowUsage
      self.response.out.write("%s" % PATH)
      self.response.out.write(sys.modules['__main__'].__doc__)
      return

    rsp = GoFetch(url, cache_life)
    if rsp:
      self.response.headers['Cache-Control'] = 'public'
      self.response.headers["Content-Type"] = 'text/xml'
      self.response.out.write(rsp)
    else:
      self.error(400)
      return

         
APP = webapp.WSGIApplication(
    [ ("%s.*" % PATH, handleRequest)
    ], debug=True)

def main():
  """ this program starts here """
  run_wsgi_app(APP)


if __name__ == '__main__':
  main()
