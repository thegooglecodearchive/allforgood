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
Data needed for live vs dev deployment.

In order to run this application, you will need the private_keys.py
file which contains the Facebook API "Application Secret" string and
other confidential config settings.
Contact footprint-eng@googlegroups.com to get this file.
"""

import os
import logging
import private_keys

PRODUCTION_DOMAINS = ['allforgood.org', 'footprint2009qa.appspot.com']

# pylint: disable-msg=C0301
MAPS_API_KEYS = {
  'www.allforgood.org' : 'ABQIAAAAHtEBbyenR4BaYGl54_p0fRQu5fCZl1K7T-61hQb7PrEsg72lpRQbhbBcd0325oSLzGUQxP7Nz9Rquw',
  'allforgood.org' : 'ABQIAAAAHtEBbyenR4BaYGl54_p0fRQu5fCZl1K7T-61hQb7PrEsg72lpRQbhbBcd0325oSLzGUQxP7Nz9Rquw',
  'footprint2009qa.appspot.com' : 'ABQIAAAA1sNtdnui_8Lmt75VBAosOhRSEEb9tdSIuCkRNLnpLNbLMSh74BRy7tIEe3Z6GgLCRLUFTTQ45vQ3mg',
  'footprint-loadtest.appspot.com' : 'ABQIAAAAxq97AW0x5_CNgn6-nLxSrxSWKH9akPVZO-6F_G0PvWoeHNZVdRSifDQCrd-osJFuWDqR3Oh0nKDgbw',
  'footprint2009dev.appspot.com' : 'ABQIAAAAxq97AW0x5_CNgn6-nLxSrxTpeCj-9ism2i6Mt7fLlVoN6HsfDBSOZjcyagWjKTMT32rzg71rFenopA',
  'mt1955.latest.servicefootprint.appspot.com' : 'ABQIAAAAienQr37mEiFBwlgibJ1JcxR1KvS2SINSTEhx6KwLmvTr3pfveRSjY7BvkzTo44hCktsrLKU800bN1g',
  'r2.latest.servicefootprint.appspot.com' : 'ABQIAAAAienQr37mEiFBwlgibJ1JcxR1KvS2SINSTEhx6KwLmvTr3pfveRSjY7BvkzTo44hCktsrLKU800bN1g',
  'r2-backup.latest.servicefootprint.appspot.com' : 'ABQIAAAAienQr37mEiFBwlgibJ1JcxR1KvS2SINSTEhx6KwLmvTr3pfveRSjY7BvkzTo44hCktsrLKU800bN1g',
  'staging.latest.footprint2009dev.appspot.com' : 'ABQIAAAAxq97AW0x5_CNgn6-nLxSrxTpeCj-9ism2i6Mt7fLlVoN6HsfDBSOZjcyagWjKTMT32rzg71rFenopA',
  'echoditto.latest.footprint2009dev.appspot.com' : 'ABQIAAAAxq97AW0x5_CNgn6-nLxSrxTpeCj-9ism2i6Mt7fLlVoN6HsfDBSOZjcyagWjKTMT32rzg71rFenopA'
}
# pylint: enable-msg=C0301

# Google Analytics keys - only needed for dev, qa, and production
# we don't want to track in other instances
GA_KEYS = {
  'www.allforgood.org' : 'UA-8689219-2',
  'allforgood.org' : 'UA-8689219-2',
  'footprint2009dev.appspot.com' : 'UA-8689219-3',
  'footprint2009qa.appspot.com' : 'UA-8689219-4'
}

# These are the public Facebook API keys.
DEFAULT_FACEBOOK_API_KEY = 'df68a40a4a90d4495ed03f920f16c333'
FACEBOOK_API_KEYS = {
  'allforgood.org': '628524bbaf79da8a8a478e5ef49fb84f',
  'footprint2009qa.appspot.com': '213e79302371015635ab5707d691143f'
}

FACEBOOK_API_KEY = None
FACEBOOK_SECRET = None
MAPS_API_KEY = None
GA_KEY = None

def host_sans_www():
  """Return the host name without any leading 'www.'"""
  http_host = os.environ.get('HTTP_HOST')
  
  # Remove www. at the beginning if it's there
  if (http_host[:4]=='www.'):
    http_host = http_host[4:]

  return http_host

def is_production_site():
  """is this a production instance?"""
  return host_sans_www() in PRODUCTION_DOMAINS

def is_local_development():
  """is this running on a development server (and not appspot.com)"""
  return (os.environ.get('SERVER_SOFTWARE').find("Development")==0)

def load_keys():
  """load facebook, maps, etc. keys."""
  global FACEBOOK_API_KEY, FACEBOOK_SECRET, GA_KEY, MAPS_API_KEY
  if FACEBOOK_API_KEY or MAPS_API_KEY or FACEBOOK_SECRET or GA_KEY:
    return

  if is_local_development():
    # to define your own keys, modify local_keys.py-- ok to checkin.
    local_keys = __import__('local_keys')
    try:
      MAPS_API_KEYS.update(local_keys.MAPS_API_KEYS)
    except:
      logging.info("local_keys.MAPS_API_KEYS not defined")
    try:
      FACEBOOK_API_KEYS.update(local_keys.FACEOOK_API_KEYS)
    except:
      logging.info("local_keys.FACEBOOK_API_KEYS not defined")

  # no default for maps api-- has to match
  http_host = host_sans_www()
  MAPS_API_KEY = MAPS_API_KEYS.get(http_host, 'unknown')
  logging.info("host=" + http_host + "  maps api key=" + MAPS_API_KEY)

  # no default for ga key
  GA_KEY = GA_KEYS.get(http_host, 'unknown')
  logging.info("host=" + http_host + "  ga key=" + GA_KEY)

  # facebook API has default key
  FACEBOOK_API_KEY = FACEBOOK_API_KEYS.get(http_host, DEFAULT_FACEBOOK_API_KEY)
  logging.debug("host=" + http_host + "  facebook key=" + FACEBOOK_API_KEY)

  # facebook secret keys are a special case
  dfl_fb_secret = None
  try:
    dfl_fb_secret = private_keys.DEFAULT_FACEBOOK_SECRET
  except:
    raise NameError("error reading private_keys.DEFAULT_FACEBOOK_SECRET-- "+
                     "please install correct private_keys.py file")
  try:
    FACEBOOK_SECRET = private_keys.FACEBOOK_SECRETS.get(
      http_host, dfl_fb_secret)
  except:
    raise NameError("error reading private_keys.FACEBOOK_SECRETS-- "+
                     "please install correct private_keys.py file")

def load_standard_template_values(template_values):
  """set template_values[...] for various keys"""
  load_keys()
  template_values['maps_api_key'] = MAPS_API_KEY
  template_values['facebook_key'] = FACEBOOK_API_KEY
  template_values['ga_key'] = GA_KEY

def get_facebook_secret():
  """Returns the facebook secret key"""
  load_keys()
  return FACEBOOK_SECRET

def get_facebook_key():
  """Returns the facebook public key"""
  load_keys()
  return FACEBOOK_API_KEY
