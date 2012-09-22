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
paths used in the app
"""
URL_HOME = '/'
URL_PARTNERS = '/partners'
URL_OLD_HOME = '/home'
URL_CONSUMER_UI_SEARCH = '/search'
URL_CONSUMER_UI_REPORT = '/report'
URL_CONSUMER_UI_SEARCH_REDIR = '/search_form'
URL_API_SEARCH = '/api/volopps'
URL_LEGACY_API_SEARCH = '/api/search'
URL_MY_EVENTS = '/myevents'
URL_FRIENDS = '/friends'
URL_POST = '/post'
URL_ADMIN = '/admin'
URL_MODERATE = '/moderate'
URL_MODERATE_BLACKLIST = '/moderateblacklist'
URL_UI_SNIPPETS = '/ui_snippets'
URL_REDIRECT = '/url'
URL_DATAHUB_DASHBOARD = '/dashboard/datahub'
URL_ACTION = '/action'  # User actions like starring
URL_PSA = '/psa' # Redirect to home page for tracking adsense psas
URL_SPEC = '/spec'
URL_SHORT_NAMES = '/s/.*'
URL_HOME4HOLIDAYS = '/home4holidays'

CONTENT_LOCATION = 'pages/'

# Mappings between appliation URLs (key) and static content
# files to fetch (CONTENT_LOCATION + value).
# So, for example, the application URL '/about' maps to
# static/about_us.html
CONTENT_FILES = {
  '/' : 'home.html',
  '/home' : 'home.html',
  '/about' : 'about_us.html',
  '/privacypolicy' : 'privacy_policy.html',
  '/contentpolicy' : 'content_policy.html',
  '/team' : 'team.html',
  '/getinvolved' : 'getinvolved.html',
  '/contactus' : 'contactus.html',
  '/spreadsheet' : 'spreadsheet.html',
  '/partners' : 'partners.html',
  '/publishers' : 'publishers.html',
  '/help' : 'help.html',
  '/gettingstarted' : 'gettingstarted.html',
  '/faq' : 'faq.html',
  '/tos' : 'tos.html',
  '/api_tos' : 'api_tos.html',
  '/apps' : 'apps.html',
  '/not_found.html' : 'not_found.html',
  '/api.html' : 'api.html',
  '/guide' : 'tour.html',
  '/cla' : 'cla.html',
  '/spec' : 'spec.html',
  '/posting' : 'spreadsheet.html',
  '/golocal' : 'cos.html',
  '/mlkdayofservice' : 'mlkdayofservice.html',
  '/apps/gmail' : 'apps-gmail.html',
  '/apps/typepad' : 'apps-typepad.html',
  '/apps/blogger' : 'apps-blogger.html',
  '/apps/googlesites' : 'apps-googlesites.html',
  '/apps/wordpress' : 'apps-wordpress.html',
}

"""
  '/code' : 'code.html',
  '/dmca' : 'dmca.html',
  '/partner_terms' : 'partner_terms.html',
"""
