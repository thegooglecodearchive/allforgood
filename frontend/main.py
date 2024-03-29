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
appengine main().
"""

from google.appengine.dist import use_library
use_library('django', '1.2')

import os
#os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'


from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
import logging

import views
import urls
import deploy

APPLICATION = webapp.WSGIApplication(
    [(urls.URL_HOME, views.home_page_view),
     (urls.URL_PARTNERS, views.partner_page_view),
     (urls.URL_OLD_HOME, views.home_page_redir_view),
     (urls.URL_DATAHUB_DASHBOARD, views.datahub_dashboard_view),
     (urls.URL_API_SEARCH, views.search_view),
     (urls.URL_UI_SNIPPETS, views.ui_snippets_view),

     (urls.URL_REDIRECT, views.redirect_view),
     (urls.URL_HOME4HOLIDAYS, views.home4holidays_redir_view), # this is a redirect

     (urls.URL_CONSUMER_UI_SEARCH_REDIR, views.consumer_ui_search_redir_view),
     (urls.URL_CONSUMER_UI_SEARCH, views.consumer_ui_search_view),
     (urls.URL_CONSUMER_UI_REPORT, views.consumer_ui_search_view),
    ] 
    + [ (url, views.static_content) for url in
         urls.CONTENT_FILES.iterkeys() ] 
    + [ ('/.*', views.not_found_handler) ],
    debug=deploy.is_local_development())


def main():
  """this comment to appease pylint."""
  if deploy.is_local_development():
    logging.info("deploy.is_local_development()==True")
  else:
    # we have lots of debug and info's
    logging.getLogger().setLevel(logging.INFO)
  run_wsgi_app(APPLICATION)

if __name__ == "__main__":
  main()
