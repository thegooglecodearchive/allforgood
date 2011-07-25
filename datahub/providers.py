#!/usr/bin/python
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

"""provider specifics"""

ProviderNames = {
  # feed_providerName:{proper_name, idx}
  "other":{"name":"Additional Partners", "idx":0}, 
  "911dayofservice":{"name":"911 National Day of Service", "idx":1}, 
  "aarp":{"name":"AARP", "idx":2}, 
  "americanredcross":{"name":"American Red Cross", "idx":3}, 
  "americansolutions":{"name":"American Solutions","idx":4}, 
  "americorps":{"name":"AmeriCorps", "idx":5}, 
  "catchafire":{"name":"Catchafire","idx":6}, 
  "christianvolunteering":{"name":"Christian Volunteering", "idx":7}, 
  "citizencorps":{"name":"Citizen Corps", "idx":8}, 
  "craigslist":{"name":"Craigs List", "idx":9}, 
  "diy":{"name":"Self-directed","idx":10}, 
  "extraordinaries":{"name":"Extraordinaries", "idx":11}, 
  "givingdupage":{"name":"Giving DuPage County a Chance","idx":12}, 
  "greentheblock":{"name":"Green the Block", "idx":13}, 
  "gspreadsheets":{"name":"Spreadsheet Provider","idx":14}, 
  "habitat":{"name":"Habitat for Humanity", "idx":15}, 
  "handsonnetwork":{"name":"HandsOn Network", "idx":16}, 
  "idealist":{"name":"Idealist", "idx":17}, 
  "meetup":{"name":"MeetUp", "idx":18}, 
  "mentor":{"name":"MENTOR", "idx":19}, 
  "mlk_day":{"name":"MLK Day", "idx":20}, 
  "mybarackobama":{"name":"My Barack Obama","idx":21}, 
  "myproj_servegov":{"name":"Serve.gov MyProject", "idx":22}, 
  "newyorkcares":{"name":"New York Cares","idx":23}, 
  "rockthevote":{"name":"Rock the Vote","idx":24}, 
  "sparked":{"name":"Sparked.com MicroVolunteering","idx":25}, 
  "seniorcorps":{"name":"Senior Corps", "idx":26}, 
  "servenet":{"name":"Serve.net", "idx":27}, 
  "servicenation":{"name":"Service Nation","idx":28}, 
  "threefiftyorg":{"name":"350.org", "idx":29}, 
  "universalgiving":{"name":"Universal Giving", "idx":30}, 
  "volunteergov":{"name":"Volunteer.gov", "idx":31}, 
  "up2us":{"name":"Up2Us","idx":32}, 
  "unitedway":{"name":"United Way", "idx":33}, 
  "volunteertwo":{"name":"Volunteer2", "idx":34}, 
  "volunteermatch":{"name":"Volunteer Match", "idx":35}, 
  "washoecounty":{"name":"Washoe County", "idx":36}, 
  "ymca":{"name":"YMCA", "idx":37}, 
  "1sky":{"name":"1Sky", "idx":38},
  "usaintlexp":{"name":"International Experience USA", "idx":39},
  "samaritan":{"name":"Samaritan Technologies", "idx":40},
}

def updateProviderNamesScript():

  js = []
  js.append('')
  js.append("arProviderNames = new Array();")

  list = []
  for k in ProviderNames.keys():
    p = ProviderNames[k]
    list.append([p["idx"], 'arProviderNames[' + str(p["idx"]) + '] = "' + p["name"] + '";'])

  def cmp_idx(a, b):
    if a[0] > b[0]:
      return 1
    if a[0] < b[0]:
      return -1
    return 0

  list.sort(cmp_idx)

  for item in list:
    js.append(item[1])

  js.append('')
  return "\n".join(js)

