# Copyright 2011 Facebook, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import private_keys

# Facebook Application ID and Secret.
# ref https://developers.facebook.com/apps/316930785030161/summary
FACEBOOK_APP_ID = '316930785030161'
FACEBOOK_APP_SECRET = private_keys.FACEBOOK_SECRETS['afg']

# Canvas Page name.
FACEBOOK_CANVAS_NAME = 'All for Good'

# A random token for use with the Real-time API.
FACEBOOK_REALTIME_VERIFY_TOKEN = 'RANDOM TOKEN'

# The external URL this application is available at where the Real-time API will
# send it's pings.
EXTERNAL_HREF = 'https://www.allforgood.org/fb/'

# Facebook User IDs of admins. The poor mans admin system.
# michael = 630488088
ADMIN_USER_IDS = ['630488088']
