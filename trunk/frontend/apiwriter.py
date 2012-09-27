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
Classes for outputting search results API in various formats.
"""

from datetime import datetime
from xml.dom.minidom import Document

import template_helpers
import api
import utils
from templatetags.dateutils_tags import custom_date_format

SEARCH_RESULTS_DEBUG_TEMPLATE = 'search_results_debug.html'

FIELD_TUPLES = [
  ('id', 'item_id'),
  ('title',),
  ('description', 'snippet'),
  ('pubDate','pubdate'),
  ('groupid', 'merge_key'),
  ('provider',),
  ('startdate', ),
  ('enddate', ),
  ('base_url',),
  ('xml_url',),
  ('url_short',),
  ('latlong',),
  ('location_name', 'location'),
  ('interest_count',),
  ('impressions',),
  ('quality_score',),
  ('categories',),
  ('categorytags',),
  ('skills',),
  ('distance',),
  #('duration',),
  ('virtual',),
  ('self_directed'),
  ('micro'),
  ('volunteers_needed'),
  ('addr1',),
  #('addrname1',),
  ('org_name',),
  ('org_organizationurl',),
  ('openEnded',),
  ('startTime',),
  ('endTime',),
  #('contactNoneNeeded',),
  ('contactEmail',),
  ('contactPhone',),
  ('contactName',),
  ('detailUrl', 'url'),
  ('audienceAll',),
  ('audienceAge',),
  ('minimumage',),
  ('audienceSexRestricted',),
  ('street1',),
  ('street2',),
  ('city',),
  ('state',),
  ('zip',),
  ('country',),
  ('affiliateorganizationname',),
  ('affiliateorganizationurl',),
  ('opportunityid',), 
  ('opportunitytype',), 
  ('registertype',), 
  ('occurrenceid',),
  ('occurrenceduration',),
  ('eventid',),
  ('eventname',),
  ('frequencyurl',), 
  ('frequency',), 
  ('availabilitydays',), 
  ('appropriatefors',), 
  ('audiencetags',), 

  ('volunteerhuborganizationurl',),
  ('volunteerhuborganizationname',),
  ('volunteersslots',),
  ('volunteersfilled',),
  ('sexrestrictedto',),
  ('eventname',),
  ('eventid',),

  ('scheduletype',), 
  ('zip',), 
]

HOC_FIELDS = [
  'org_name',
  'org_organizationurl',
  'volunteerhuborganizationurl',
  'volunteerhuborganizationname',
  'volunteersslots',
  'volunteersfilled',
  'affiliateorganizationurl',
  'affiliaterganizationname',

  'eventid',
  'eventname',

  'managedby',
  'minimumage',

  'opportunityid',
  'opportunitytype',
  'registertype',
  'occurrenceid',
  'occurrenceduration',
  'frequencyurl',
  'frequency',
  'availabilitydays',
  'appropriatefors',
  'audiencetags',
  'categorytags',

  'eventrangestart',
  'eventrangeend',

  'distance',

  'contactemail',
  'contactphone',
  'scheduletype',
  'audienceage',
  'sexrestrictedto',
  'street1',
  'street2',
  'state', 'zip', 'postalcode',
]

API_FIELD_NAMES_MAP = {
  # solr/result : json/rss output
  'item_id' : 'id',
  'org_name' : 'sponsoringOrganizationName',
  'org_organizationurl' : 'sponsoringOrganizationURL',
  'startdate' : 'startDate',
  'enddate' : 'endDate',
  'scheduletype' : 'scheduleType',
  'activitytype' : 'activityType',
  'invitationcode' : 'invitationCode',
  'managedby' : 'managedBy',
  'registertype' : 'registerType',
  'affiliateid' : 'affiliateId',
  'occurrenceduration' : 'occurrenceDuration',
  'occurrenceid' : 'occurrenceId',
  'isdisaster' : 'isDisaster',
  'opportunitytype' : 'opportunityType',
  'registertype' : 'registerType',
  'opportunityid' : 'opportunityId',
  'location' : 'location_name',

  'snippet' : 'description',
  'url' : 'detailUrl',

  'categorytags' : 'categoryTags',

  'availabilitydays' : 'availabilityDays', 
  'appropriatefors' : 'appropriateFors', 
  'audiencetags' : 'audienceTags', 

  'dayweek' : 'dayWeek',
  'distance' : 'Distance', 

  'managedby' : 'managedBy',
  'minimumage' : 'minAge',

  'org_organizationurl' : 'sponsoringOrganizationUrl',
  'volunteerhuborganizationurl' : 'volunteerHubOrganizationUrl',
  'volunteerhuborganizationname' : 'volunteerHubOrganizationName',
  'affiliateorganizationurl' : 'affiliateOrganizationUrl',
  'affiliateorganizationname' : 'affiliateOrganizationName',

  'occurrenceid' : 'occurrenceId',
  'eventname' : 'eventName',
  'eventid' : 'eventId',

  'state' : 'region',
  'zip' : 'postalCode', 'postalcode' : 'postalCode',
  'audiencesexrestricted' : 'audienceSexRestricted',

  'contactemail' : 'contactEmail',
  'contactphone' : 'contactPhone',
  'contactname' : 'contactName',

  'frequencyurl' : 'frequencyURL',
  'frequencylink' : 'frequencyLink',

  'eventname' : 'eventName',
  'eventid' : 'eventId',

  'volunteersslots' : 'volunteersNeeded',
  'volunteersfilled' : 'rsvpCount',
}

STANDARD_FIELDS = [
  'id', 
  'item_id',
  'title',
  'description', 
  'snippet',
  'pubdate',
  'groupid', 
  'merge_key',
  'provider',
  'startdate', 
  'enddate',
  'base_url',
  'xml_url',
  'url_short',
  'latlong',
  'location_name', 
  'location',
  'interest_count',
  'impressions',
  'quality_score',
  'categories',
  'skills',
  'virtual',
  'self_directed',
  'micro',
  'volunteers_needed',
  'addr1',
  'addrname1', 
  'sponsoringorganizationname',
  'orgname',
  'openended',
  'starttime',
  'endtime',
  'contactnoneneeded',
  'contactemail',
  'contactphone',
  'contactname',
  'detailurl',
  'audienceall',
  'audienceage',
  'minage',
  'audiencesexrestricted',
  'street1',
  'street2',
  'city',
  'state',
  'zip', 'postalcode',
  'country',
  'minimumage',
  'contactnoneneeded',
]

CALENDAR_FIELDS = [
  'org_name',
  'startdate', 
  'enddate',
  'minage',
  'contactphone',
  'quality_score',
  'detailurl',
  'sponsoringorganizationname',
  'sponsoringorganizationurl',
  'volunteerhuborganizationname',
  'volunteerhuborganizationurl',
  'volunteersfilled',
  'volunteersslots',
  'latlong',
  'contactname',
  'addr1',
  'impressions',
  'id',
  'city',
  'occurrenceduration',
  'distance',
  'opportunityid',
  'occurrenceid',
  'location_name',
  'openended',
  'pubdate',
  'title',
  'base_url',
  'virtual',
  'provider',
  'zip', 'postalcode',
  'distance',
  'groupid',
  'audienceage',
  'audienceall',
  'eventid',
  'description',
  'street1',
  'street2',
  'interest_count',
  'xml_url',
  'audiencesexrestricted',
  'starttime',
  'contactnoneneeded',
  'categories',
  'contactemail',
  'skills',
  'country',
  'state',
  'url_short',
  'addrname1',
  'endtime',
  'volunteersneeded',
  'rsvpcount',  
  'scheduletype',
  'opportunitytype',
]

ARRAY_FIELDS = [
  'audienceTags', 
  'availabilityDays', 
  'appropriateFors', 
  'categoryTags', 
  'skills',
  'categories',
]

def get_writer(output):
  """Returns the appropriate ApiWriter class for the requested output type."""
  if output.find('rss') >= 0:
    return RssApiWriter('application/rss+xml')
  elif output.find('json') >= 0:
    return JsonApiWriter('application/javascript')
  else:
    #default to Debug HTML
    return DebugHtmlApiWriter('text/html')

class ApiWriter:
  """Base class for all ApiWriter classes."""
  def __init__(self, content_type):
    """Initializer, content_type will be the expected output type."""
    self.content_type = content_type
  
  def setup(self, request, result_set):
    """Do any setup based on the result set here."""
    pass
  
  def add_result(self, result, result_set = {}):
    """Process one result item at a time."""
    pass
  
  def finalize(self):
    """Finalize the results, and return them as a string."""
    return None
  
class DjangoTemplateApiWriter(ApiWriter):
  """Base class for any API output we still want to use Django templates for."""
  
  def __init__(self, content_type):
    ApiWriter.__init__(self, content_type)
    self.template = None
    self.template_values = None
    self.result_set = None
    
  def setup(self, request, result_set):
    """setup the template we will use"""
    self.result_set = result_set
    self.template_values = template_helpers.get_default_template_values(
      request, 'SEARCH')
    self.template_values.update({
        'result_set': result_set,
        'latlong': result_set.args["latlong"],
        'keywords': result_set.args[api.PARAM_Q],
        'location': result_set.args[api.PARAM_VOL_LOC],
        'max_distance': result_set.args[api.PARAM_VOL_DIST],
      })

    if result_set.is_hoc:
      self.template_values.update({
        'facets' : {}
      })
      
      if not result_set.is_cal:
        self.template_values.update({
          'TotalOpportunities': 0, 
          'TotalMatch': 0, 
        })
      
  
  def finalize(self):
    """return the rendered template"""
    return template_helpers.render_template(self.template, self.template_values)

class DebugHtmlApiWriter(DjangoTemplateApiWriter):
  """Output human readable HTML for debugging."""
  
  def __init__(self, content_type):
    """Set the template to use."""
    DjangoTemplateApiWriter.__init__(self, content_type)
    self.template = SEARCH_RESULTS_DEBUG_TEMPLATE
          
  def add_result(self, result, result_set = {}):
    pass
      
class JsonApiWriter(ApiWriter):
  """Outputs the search results as JSON."""
  
  # Fields we output per item
  item_fields = FIELD_TUPLES
  
  def __init__(self, content_type):
    """No special initialization."""
    self.items = None
    self.json = None
    ApiWriter.__init__(self, content_type)
    
  def setup(self, request, result_set):
    """Setup a dict that will eventually be converted to JSON."""
    self.json = {
      'version' : 1.0,
      'href' : result_set.request_url,
      'description' : 'All for Good search results',
      'language' : 'en-us',
      'lastBuildDate' : result_set.last_build_date,
      'items' : []
    }

    if result_set.is_hoc:
      self.json['facets'] = {}
      for facet, facet_list in result_set.hoc_facets.items():
        if facet_list:
          self.json['facets'][facet] = {}
          facet_name = facet_value = ''
          for fv in facet_list:
            if not facet_name:
              facet_name = fv
              facet_value = ''
            elif not facet_value:
              facet_value = fv
              self.json['facets'][facet][facet_name] = facet_value
              facet_name = facet_value = ''

      if not result_set.is_cal:
        self.json['TotalOpportunities'] = result_set.total_opportunities
        self.json['TotalMatch'] =  result_set.total_match

    self.items = self.json['items']
    
    if result_set.is_hoc or result_set.is_json2 or result_set.is_exelis:
      self.json['num'] = len(result_set.clipped_results)
      self.json['MergedCount'] = result_set.merged_count
      self.json['BackendCount'] = result_set.backend_count
 
        
  def add_result(self, result, result_set = {}):
    """Add an item dict to the items array."""
    #result is instance of SearchResult

    item = {}
    for field_info in self.item_fields:
      name = field_info[0]
      if result_set.is_hoc and name.lower() not in utils.unique_list(STANDARD_FIELDS + HOC_FIELDS):
        continue

      if result_set.is_cal and name.lower() not in CALENDAR_FIELDS:
        continue

      if not hasattr(result, name):
        name = name.lower()
        if not hasattr(result, name) and len(field_info) > 1:
          name = field_info[1]
          if not hasattr(result, name):
            name = name.lower()

      content = getattr(result, name, '')
        
      if name.lower() == "enddate":
        if custom_date_format(content) == 'Present':
          content = ''
      elif name == "description":
        if result_set.args.get('fulldesc', '') != '1':
          content = content[:300]
      elif name in ["eventrangestart", "eventrangeend"]:
        content = content.replace('T', ' ').strip('Z')

      # handle lists
      if isinstance(content, basestring) and content.find('\t') > 0:
        item[API_FIELD_NAMES_MAP.get(name, name)] = content.split('\t')
      elif API_FIELD_NAMES_MAP.get(name, name) in ARRAY_FIELDS and not isinstance(content, list):
        if content:
          item[API_FIELD_NAMES_MAP.get(name, name)] = [content]
        else:
          item[API_FIELD_NAMES_MAP.get(name, name)] = []
      else:
        item[API_FIELD_NAMES_MAP.get(name, name)] = content

    self.items.append(item)
    
  def finalize(self):
    """Convert the dict to a JSON string."""
    from django.utils import simplejson
    class MyEncoder(simplejson.JSONEncoder):
      """JSONEncoder doesn't handle datetime, so we have to extend it."""
      datetime_class = type(datetime)
      def default(self, obj):
        """If the obj is a datetime, return it as a string."""
        if isinstance(obj, datetime):
          return str(obj)
        return simplejson.JSONEncoder.default(self, obj)
    encoder = MyEncoder(indent=1)
    return encoder.encode(self.json)

  
class RssApiWriter(ApiWriter):
  """Output the search results as an RSS data feed."""
  
  OurNamespace = "fp" #TODO change to afg?

  def __init__(self, content_type):
    """No special initialization."""
    self.doc = None
    self.rss = None
    self.channel = None
    ApiWriter.__init__(self, content_type)
    
  def setup(self, request, result_set):
    """
    Create the RSS preamble, everything before the results list.
    """
    self.doc = Document()
    self.rss = self.doc.createElement('rss')
    self.rss.setAttribute('version','2.0')
    self.rss.setAttribute('xmlns:georss', "http://www.georss.org/georss")
    self.rss.setAttribute('xmlns:gml', "http://www.opengis.net/gml")
    self.rss.setAttribute('xmlns:atom', "http://www.w3.org/2005/Atom")
    self.rss.setAttribute('xmlns:' + self.OurNamespace,
                          "http://www.allforgood.org/")
    self.doc.appendChild(self.rss)
    channel = self.doc.createElement('channel')
    self.rss.appendChild(channel)
    
    def create_text_element(parent, name, content=None, attrs = None):
      elem = self.doc.createElement(name)
      if attrs:
        for k, v in attrs.items():
          elem.setAttribute(k, v)

      parent.appendChild(elem)
      if content != None:
        elem.appendChild(self.doc.createTextNode(str(content)))
      return elem
    
    create_text_element(channel, 'title', 'All for Good search results')
    create_text_element(channel, 'link', 'http://www.allforgood.org/')
    
    atom_link = self.doc.createElement('atom:link')
    channel.appendChild(atom_link)
    atom_link.setAttribute('href', result_set.request_url)
    atom_link.setAttribute('rel', 'self')
    atom_link.setAttribute('type', str(self.content_type))
    
    create_text_element(channel,
                        'description',
                        'All for Good search results')
    create_text_element(channel, 'language', content='en-us')
    create_text_element(channel, 'pubDate') #TODO: fill this in
    create_text_element(channel,
                        'lastBuildDate',
                        content=result_set.last_build_date)

    if result_set.is_hoc:
      facets_node = create_text_element(channel, 'facets')
      for facet, facet_list in result_set.hoc_facets.items():
        if facet_list:
          facet_node = create_text_element(facets_node, 'facet', None, {'name' : facet})
          facet_name = facet_value = ''
          for fv in facet_list:
            if not facet_name:
              facet_name = fv
              facet_value = ''
            elif not facet_value:
              facet_value = fv
              facet_value_node = create_text_element(facet_node, 'count', facet_value, {'name' : facet_name})
              facet_name = facet_value = ''
          
      if not result_set.is_cal:
        create_text_element(channel,
                            'TotalMatch',
                            content=str(result_set.total_match))
        create_text_element(channel,
                            'TotalOpportunities',
                            content=str(result_set.total_opportunities))

    self.channel = channel
    
  def add_result(self, result, result_set = {}):
    """
    Add an <item/> stanza to the results.  The stanza will include the required
    RSS elements, plus our own namespaced elements.
    """
    def build_result_element(field_info, result):

      content = ''
      name = field_info[0]
      if not hasattr(result, name) and len(field_info) > 1:
        name = field_info[1]

      if hasattr(result, name):
        try:
          content = str(getattr(result, name, ''))
        except UnicodeEncodeError:
          content = getattr(result, name, '').encode('ascii', 'ignore')

      if name == "enddate": 
        if custom_date_format(content) == 'Present':
          content = ''
      elif name == "description":
        if result_set.args.get('fulldesc', '') != '1':
          content = content[:300]
      elif name in ["eventrangestart", "eventrangeend"]:
        content = content.replace('T', ' ').strip('Z')

      return (name, content, None)
    
    item = self.doc.createElement('item')
    self.channel.appendChild(item)
    
    #standard RSS fields
    standard_fields = [
      ('title',),
      ('link', 'xml_url'),
      ('description', 'snippet'),
      ('pubDate',), 
      ('guid', 'xml_url')
    ]
    added_list = []
    for field in standard_fields:
      (name, content, comment) = build_result_element(field, result)
      if len(name) < 3:
        continue

      if name == 'xml_url':
        name = 'link'
      else:
        name = API_FIELD_NAMES_MAP.get(name, name)

      if name in added_list:
        continue
      added_list.append(name)

      if comment:
        item.appendChild(self.doc.createComment(comment))
      subitem = self.doc.createElement(name)
      if content:
        text = self.doc.createTextNode(content)
        subitem.appendChild(text)
      item.appendChild(subitem)

    #and now our namespaced fields
    namespaced_fields = FIELD_TUPLES

    added_list = []
    for field_info in namespaced_fields:
      (name, content, comment) = build_result_element(field_info, result)

      name = self.OurNamespace + ':' + API_FIELD_NAMES_MAP.get(name, name)

      if not result_set.is_hoc and name.lower() not in STANDARD_FIELDS:
        continue

      if result_set.is_cal and name.lower() not in CALENDAR_FIELDS:
        continue

      if name in added_list:
        continue
      added_list.append(name)

      if comment:
        item.appendChild(self.doc.createComment(comment))

      subitem = self.doc.createElement(name)
      if content:
        if len(field_info) > 1 and isinstance(content, basestring) and content.find('\t') > 0:
          content = content.split('\t')

        if isinstance(content, list):
          for value in content:
            subsubitem = self.doc.createElement(self.OurNamespace + ':' + field_info[1])
            text = self.doc.createTextNode(value)
            subsubitem.appendChild(text)
            subitem.appendChild(subsubitem)
        else:
          text = self.doc.createTextNode(content)
          subitem.appendChild(text)
          
      item.appendChild(subitem)
      
  def finalize(self):
    """Return a string from the XML document."""
    #return self.doc.toxml(encoding='utf-8')
    return self.doc.toprettyxml(indent='  ', newl='\n', encoding='utf-8')
