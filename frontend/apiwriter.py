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
from fastpageviews import pagecount
from templatetags.dateutils_tags import custom_date_format

SEARCH_RESULTS_DEBUG_TEMPLATE = 'search_results_debug.html'

def get_writer(output):
  """Returns the appropriate ApiWriter class for the requested output type."""
  if output == 'rss':
    return RssApiWriter('application/rss+xml')
  elif output == 'json':
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
  
  def add_result(self, result):
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
        # TODO: remove this stuff...
        'latlong': result_set.args["latlong"],
        'keywords': result_set.args[api.PARAM_Q],
        'location': result_set.args[api.PARAM_VOL_LOC],
        'max_distance': result_set.args[api.PARAM_VOL_DIST],
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
          
  def add_result(self, result):
    """Add the per-result debug information."""
    result.merged_clicks = pagecount.GetPageCount(
      pagecount.CLICKS_PREFIX+result.merge_key)
    if result.merged_impressions < 1.0:
      result.merged_ctr = "0"
    else:
      result.merged_ctr = "%.2f" % (
        100.0 * float(result.merged_clicks) / float(result.merged_impressions))
      
class JsonApiWriter(ApiWriter):
  """Outputs the search results as JSON."""
  
  #Fields we output per item
  item_fields = [
    ('id', 'item_id'),
    ('title',),
    ('description', 'snippet'),
    ('pubDate',),
    # groupid is a stable ID for the dedup'd set of results, 
    #   including same listing but different time/location 
    ('groupid', 'merge_key'),
    ('provider',),
    ('startDate', 'startdate'),
    ('endDate', 'enddate'),
    ('base_url',),
    ('xml_url',),
    ('url_short',),
    ('latlong',),
    ('location_name', 'location'),
    ('interest_count',),
    ('impressions',),
    ('quality_score',),
    ('categories',),
    ('skills',),
    ('virtual',),
    ('self_directed'),
    ('volunteers_needed'),
    ('addr1', 'addr1',
     "addr1 may change; contact core eng team before using"),
    ('addrname1', 'addrname1',
     "addrname1 may change; contact core eng team before using"),
    ('sponsoringOrganizationName', 'orgName'),
    ('openEnded',),
    ('startTime',),
    ('endTime',),
    ('contactNoneNeeded',),
    ('contactEmail',),
    ('contactPhone',),
    ('contactName',),
    ('detailUrl',),
    # TODO: make something better than weekly #
    # TODO: make something better than biweekly #
    # TODO: make something better than recurrence #
    ('audienceAll',),
    ('audienceAge',),
    ('minAge',),
    ('audienceSexRestricted',),
    # TODO: sexRestrictedTo - ref policy team #
    # TODO: make something better than commitmentHoursPerWeek #
    ('street1',),
    ('street2',),
    ('city',),
    ('region',),
    ('postalCode',),
    ('country',)
  ]
  
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
    self.items = self.json['items']
        
  def add_result(self, result):
    """Add an item dict to the items array."""
    item = {}
    for field_info in self.item_fields:
      if len(field_info) == 1:
        name = field_info[0]
        content = getattr(result, name, '')
        item[name] = content
      else:
        name = field_info[0]
        attr = field_info[1]
        if (name == "endDate" and 
            custom_date_format(getattr(result, attr)) == 'Present'):
          content = ''
        else:
          content = getattr(result, attr, '')

        item[name] = content
        #TODO: figure out a way to add comments to JSON
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
    
    def create_text_element(parent, name, content=None):
      elem = self.doc.createElement(name)
      parent.appendChild(elem)
      if content != None:
        elem.appendChild(self.doc.createTextNode(content))
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
    self.channel = channel
    
  def add_result(self, result):
    """
    Add an <item/> stanza to the results.  The stanza will include the required
    RSS elements, plus our own namespaced elements.
    """
    def build_result_element(field_info, result):
      """
      sub function to map RSS elements to result attributes.
      fieldInfo is a tuple.  
      If len(tuple) == 1, then use the value as both the name of the XML element
      and the attribute to query the result object on.
      If len(tuple) >= 2, then use tuple[0] as the XML element name and
      tuple[1] as the attribute to query.
      And finally, if tuple[2] exists, it's a comment that should be
      inserted into the XML before the element.
      """
      comment = None
      if len(field_info) == 1:
        name = field_info[0]
        if hasattr(result, name):
          try:
            content = str(getattr(result, name))
          except UnicodeEncodeError:
            content = getattr(result, name).encode('ascii','ignore')
        else:
          content = ''
      else:
        name = field_info[0]
        attr = field_info[1]
        if hasattr(result, attr):
          try:
            if (name == "endDate" and
                custom_date_format(getattr(result, attr)) == 'Present'):
              content = ''
            else:
              content = str(getattr(result, attr))
          except UnicodeEncodeError:
            content = getattr(result, attr).encode('ascii','ignore')
        else:
          content = ''
        if len(field_info) == 3:
          #has a comment
          comment = field_info[2]
      return (name, content, comment)
    
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
    for field in standard_fields:
      (name, content, comment) = build_result_element(field, result)
      if comment:
        item.appendChild(self.doc.createComment(comment))
      subitem = self.doc.createElement(name)
      if content:
        text = self.doc.createTextNode(content)
        subitem.appendChild(text)
      item.appendChild(subitem)

    #and now our namespaced fields
    namespaced_fields = [
      ('id', 'item_id'),
      # groupid is a stable ID for the dedup'd set of results, 
      #   including same listing but different time/location 
      ('groupid', 'merge_key'),
      ('provider',),
      ('startDate', 'startdate'),
      ('endDate', 'enddate'),
      ('base_url',),
      ('xml_url',),
      ('url_short',),
      ('latlong',),
      ('location_name', 'location'),
      ('interest_count',),
      ('impressions',),
      ('quality_score',),
      ('categories', 'categories_api_str'),
      ('skills',),
      ('virtual',),
      ('self_directed'),
      ('volunteers_needed'),
      ('addr1', 'addr1',
       "addr1 may change; contact core eng team before using"),
      ('addrname1', 'addrname1',
       "addrname1 may change; contact core eng team before using"),
      ('sponsoringOrganizationName', 'orgName'),
      ('openEnded',),
      ('startTime',),
      ('endTime',),
      ('contactNoneNeeded',),
      ('contactEmail',),
      ('contactPhone',),
      ('contactName',),
      ('detailUrl',),
      # TODO: make something better than weekly #
      # TODO: make something better than biweekly #
      # TODO: make something better than recurrence #
      ('audienceAll',),
      ('audienceAge',),
      ('minAge',),
      ('audienceSexRestricted',),
      # TODO: sexRestrictedTo - ref policy team #
      # TODO: make something better than commitmentHoursPerWeek #
      ('street1',),
      ('street2',),
      ('city',),
      ('region',),
      ('postalCode',),
      ('country',)
    ]
    for field in namespaced_fields:
      (name, content, comment) = build_result_element(field, result)
      name = self.OurNamespace + ':' + name 
      if comment:
        item.appendChild(self.doc.createComment(comment))
      subitem = self.doc.createElement(name)
      if content:
        text = self.doc.createTextNode(content)
        subitem.appendChild(text)
      item.appendChild(subitem)
      
  def finalize(self):
    """Return a string from the XML document."""
    return self.doc.toxml(encoding='utf-8')
    # or use toprettyxml(indent='  ', newl='\n', encoding='utf-8')
