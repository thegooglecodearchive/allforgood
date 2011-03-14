# Copyright 2009 Google Inc.  All Rights Reserved.
#

import cgi
import os

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

import pagecount

TEST_PAGEVIEWS_TEMPLATE = 'test_pageviews.html'

def RenderTemplate(template_filename, template_values):
  path = os.path.join(os.path.dirname(__file__), template_filename)
  return template.render(path, template_values)

class TestPageViewsView(webapp.RequestHandler):
  def get(self):
    pagename = "testpage:%s" % (self.request.get('pagename'))
    pc = pagecount.IncrPageCount(pagename, 1)
    template_values = pagecount.GetStats()
    template_values['pagename'] = pagename
    template_values['pageviews'] = pc
    self.response.out.write(RenderTemplate(TEST_PAGEVIEWS_TEMPLATE,
                                           template_values))

class NopView(webapp.RequestHandler):
  def get(self):
    self.response.out.write("hello world")


