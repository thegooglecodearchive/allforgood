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


from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
import os
import logging

import views
import urls
import deploy

APPLICATION = webapp.WSGIApplication(
    [(urls.URL_HOME, views.home_page_view),
     (urls.URL_PSA, views.home_page_view),
     # TODO: replace with a generic way to redirect all unknown pages to /
     (urls.URL_OLD_HOME, views.home_page_redir_view),
     (urls.URL_CONSUMER_UI_SEARCH, views.consumer_ui_search_view),
     (urls.URL_CONSUMER_UI_SEARCH_REDIR, views.consumer_ui_search_redir_view),
     (urls.URL_API_SEARCH, views.search_view),
     (urls.URL_UI_SNIPPETS, views.ui_snippets_view),
     (urls.URL_UI_MY_SNIPPETS, views.ui_my_snippets_view),
     (urls.URL_MY_EVENTS, views.my_events_view),
     (urls.URL_ACTION, views.action_view),
     (urls.URL_ADMIN, views.admin_view),
     (urls.URL_POST, views.post_view),
     (urls.URL_REDIRECT, views.redirect_view),
     (urls.URL_MODERATE, views.moderate_view),
     (urls.URL_MODERATE_BLACKLIST, views.moderate_blacklist_view),
     (urls.URL_DATAHUB_DASHBOARD, views.datahub_dashboard_view),
     (urls.URL_SPEC, views.spec_view),
     (urls.URL_SHORT_NAMES, views.short_name_view),
     (urls.URL_APPS, views.apps_view),
     (urls.URL_COS, views.cos_view),
     (urls.URL_MLKDAYOFSERVICE, views.mlkdayofservice_view),
     (urls.URL_HOME4HOLIDAYS, views.home4holidays_redir_view)
    ] +
    [ (url, views.static_content) for url in
         urls.STATIC_CONTENT_FILES.iterkeys() ] + 
    [ ('/.*', views.not_found_handler) ],
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
