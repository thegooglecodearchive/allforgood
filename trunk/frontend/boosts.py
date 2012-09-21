# Copyright 2009 Google Inc.  #
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
toss all the one-off boosts into one place (rather than a class file)
"""

DEFAULT_BOOSTS = [
  # boosting vetted categories
  ' categories:vetted^15',

  # big boost for events starting in the near future
  ' eventrangestart:[NOW TO NOW+1MONTHS]^10',

  # big boost for events ending in the near future
  ' eventrangeend:[NOW TO NOW+1MONTHS]^10',

  # slight penalty for girl scout events
  ' (*:* -feed_providername:girlscouts)^200',
  
  # slight penalty for idealist events until they can get date issue resolved
  ' (*:* -feed_providername:idealist)^100',

]

CATEGORY_QUERIES = {
  'category:mlkday' : '(mlkday OR -2009 OR -2010 OR -2011 OR -feed_providername:girlscouts OR (-feed_providername:idealist AND eventrangestart:[0001-01-01T00:00:00Z TO 2012-01-22T23:59:59Z] AND eventrangeend:[2012-01-07T00:00:00Z TO *]))',

  'category:september11' : '(september11 OR (eventrangestart:[0001-01-01T00:00:00Z TO 2012-09-13T23:59:59Z]) AND (eventrangeend:[2012-09-09T00:00:00Z TO *]))',

  'category:IAMS' : '(-PETA AND (dog OR cat OR pet) AND (shelter OR adoption OR foster))',

  'category:education' : '((education OR tutoring) AND -feed_providername:girlscouts AND -prison AND -prisoner AND -inmate AND -disaster AND -emergency)',
}

CATEGORY_BOOSTS = {
  'category:mlkday' : ' aggregatefield:(mlkday)^100 eventrangestart:[2012-01-16T00:00:00Z TO 2012-01-16T23:59:59Z]^20 eventrangeend:[2012-01-16T00:00:00Z TO 2012-01-16T23:59:59Z]^10' ,

  'category:education' : ' title:(tutor OR school OR children OR student OR classroom)^100',
  
  'category:september11' : ' title:(september11)^100 description:911day^10',
}

API_KEY_QUERIES = {
  'americanexpress' : '(911day OR (eventrangestart:[0001-01-01T00:00:00Z TO 2012-09-25T00:00:00Z] AND eventrangeend:[2012-08-30T00:00:00Z TO *]))',
	
  '911Day' : '(911day OR (eventrangestart:[0001-01-01T00:00:00Z TO 2012-10-15T00:00:00Z] AND eventrangeend:[2012-08-11T00:00:00Z TO *]))',
		
  'joiningforces' : '(military OR veteran)',
		
  'genonsite' : '(minimumage:[1 TO 17] AND (feed_providername:handsonnetworkconnect OR feed_providername:samaritan))',
  
  # commenting out new daytabank custom query pending confirmation on what is appropriate to show or not.	
  #'daytabank':'(eventrangestart:[0001-01-01T00:00:00Z TO 2011-10-22T23:59:59Z] AND eventrangeend:[2011-10-22T00:00:00Z TO *])',
}


API_KEY_BOOSTS = {
  'liveunited' : ' feed_providername:unitedway^2000 feed_providername:handsonnetwork1800^10 feed_providername:handsonnetworkconnect^10',

  'americanexpress' : ' title:911day^1000 description:911day^100 feed_providername:handsonnetwork1800^2000 feed_providername:handsonnetworkconnect^2000',
  
  '911Day' : ' title:911day^1000 description:911day^100 feed_providername:handsonnetwork1800^2000 feed_providername:handsonnetworkconnect^2000 feed_providername:handsonnetworktechnologies^2000',
  
  'daytabank' : ' feed_providername:handsonnetwork1800^1000 feed_providername:handsonnetworkconnect^1000 feed_providername:handsonnetworktechnologies^1000 feed_providername:daytabank^2000 (eventrangestart:[2012-10-22T00:00:00Z TO 2012-10-22T23:59:59Z])^1000',
    
  'joiningforces' : ' title:military^1 description:military^5 (*:* -description:veteran)^5 (*:* -org_name:spouse)^10 (*:* -title:invasive)^2000',
  
  'exelis' : ' feed_providername:handsonnetworkconnect^100 affiliateorganizationid:2002^1000 detailurl:http*signupandserve*^1000 aggregatefield:(military OR veteran)^3',

}

API_KEY_FILTER_QUERIES = {
  'starbucks' : '-provider_proper_name_str:[* TO F*] AND  -provider_proper_name_str:[Gir* TO H*] AND  -provider_proper_name_str:[I* TO *]',

  '243234' : '-feed_providername:aarp AND -feed_providername:meetup AND -feed_providername:mybarackobama',

  'hilton' : '-provider_proper_name_str:[* TO G*] AND -provider_proper_name_str:[I* TO *]',
}

API_KEY_NEGATED_FILTER_QUERIES = {
  # eg, "if not starbucks..."
  'starbucks' : '-feed_providername:getinvolved',

  # commented out filtering to prevent Blueprint opps from showing up in any queries other than on Exelis.	
  #'exelis' : '-detailurl:http*signupandserve*',
}

FILTER_QUERIES = [
]
