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

"""Contains Tagger classes used in footprint_lib.py to tag listings"""

import xml_helpers as xmlh

# Different Record classes are used to represent volunteer listings that are
# being run through the taggers in different formats.  Each class must have
# get_val(field) and add_tag(tag) functions that access data about the listing
# and add a tag to the 'categories' field, respectively.

class XMLRecord(object):
  """Stores a record in xml dom form, used in footprint_lib.py"""
  def __init__(self, opp):
    """initialize record from dom record opp"""
    self.opp = opp
  
  def get_val(self, field):
    """return a value for this record"""
    return xmlh.get_tag_val(self.opp, field)
  
  def add_tag(self, tag):
    """add a tag to the record""" 
    newnode = self.opp.createElement('categories')
    newnode.appendChild(self.opp.createTextNode(str(tag)))
    self.opp.firstChild.appendChild(newnode)

class DictRecord(object):
  """Stores a record in dict form, used when tagging TSV files"""
  def __init__(self, fields, row):
    """initialize record with list of field names and list of values"""
    self.record = dict(zip(fields.split(), row.split()))
  
  def get_val(self, field):
    """return a value for this record"""
    return self.record[field]
  
  def add_tag(self, tag):
    """add a tag to the record"""
    if len(self.record['c:categories:string']) > 0:
      self.record['c:categories:string'] += ";;"
    self.record['c:categories:string'] += tag

class Tagger(object):
  """Base class for all Taggers. Each instancetags multiple records"""
  def __init__(self, tag_name):
    """Initialize tag name and score threshold from args"""
    self.tag_name = tag_name # The tag this will apply - set in the subclass
    self.score_threshold = 1.0 # Score (between 0 and 1) necessary to apply tag

    # Each Tagger has one or more tagging functions, defined in subclasses.
    # Tagging functions take a record as an input and return a score
    # between 0.0 and 1.0.  The scores are then averaged and compared
    # to the threshold.  This is a list because a subclass of Tagger can inherit
    # from multiple types of Taggers.
    self.tagging_functions = []

  
  def do_tagging(self, rec):
    """takes a record to be tagged, runs tagging functions"""
    scores = [f(rec) for f in self.tagging_functions]
    
    # get the average score from the tagging functions
    if len(scores) > 0:
      score = sum(scores) / len(scores)
    else:
      score = 0.0
    
    # add tag if the score, after all tagging functions, exceeds the threshold
    if score > self.score_threshold:
      rec.add_tag(self.tag_name)
    
    return rec

class KeywordTagger(Tagger):
  """KeywordTagger is a base class for all Taggers that apply basic tagging 
  rules based on if a keyword appears in the description of a listing."""
  def __init__(self, tag_name, keywords_dict):
    """Create relevant variables for the KeywordTagger."""
    Tagger.__init__(self, tag_name)    
    # self.keywords holds the keywords that trigger this tag, along with the
    # amount to increment the score by (between 0.0 and 1.0) for each keyword.
    self.keywords = keywords_dict
    self.examine_fields = ['title', 'description']
    
    self.score_threshold = 0.0 # right now, we'll tag if any keywords match
    self.tagging_functions.append(self.tag_by_keywords)
  
  def tag_by_keywords(self, rec):
    """Takes the keywords defined in subclasses and checks them against
    the description, returning the average score."""
    score = 0.0
    for keyword in self.keywords:
      keyword_count = 0
      # Lowercase the keyword and replace + with space for multiple word
      # support, then add surrounding spaces
      keyword_find = ' ' + keyword.lower().replace(' +', ' ') + ' '
      for field in self.examine_fields:
        # Count the number of occurences of the modified keyword
        # in the value for this field
        keyword_count += rec.get_val(field).lower().count(keyword_find)
      if keyword_count > 0:
        score += self.keywords[keyword]
    score /= len(self.keywords)
    return score

class WSVKeywordTagger(KeywordTagger):
  """Creates a KeywordTagger from a whitespace separated list of keywords
  rather than a dict, with each keyword having a score of 1.0. 
  Supports phrases by separating words with +'s."""
  def __init__(self, tag_name, keywords_list):
    """Expand the whitespace separated list and call the KeywordTagger init"""
    keywords_dict = dict(zip(keywords_list.split(),
      [1.0]*len(keywords_list.split())))
    KeywordTagger.__init__(self, tag_name, keywords_dict)

# Right now, EducationTagger is implemented just as an instance of
# KeywordTagger, but in the future it may want to inherit from multiple
# Tagger types.  This code is how it would be implemented as a subclass.
# class EducationTagger(KeywordTagger):
#  def __init__(self):
#    KeywordTagger.__init__(self, 'Education', {'education':1.0, 'school':1.0,
#                      'teacher':1.0, 'classroom':1.0, 'leaning':1.0}) 

def get_taggers():
  """returns the current tagger instances we're using"""
  
  # Create basic keyword taggers

  # The taggers below use the WSVKeywordTagger to easily tag without
  # creating a dict with individual scores for each keyword.  The commented
  # code below shows how to create a standard KeywordTagger when we're
  # ready to assign individual scores

  # nature_tagger = KeywordTagger('Nature', {'environment':1.0, 'nature':1.0,
  # 'environmental':1.0, 'outdoors':1.0, 'gardening':1.0, 'garden':1.0,
  # 'park':1.0, 'wetlands':1.0,'forest':1.0, 'trees':1.0})

  nature_tagger = WSVKeywordTagger('Nature', 'environment nature ' +
    'environmental outdoors gardening garden park wetlands forest forests ' +
    'tree trees green trail trails sierra+club ')
  
  education_tagger = WSVKeywordTagger('Education', 'education reading ' +
    'teaching teacher teach books book library literacy school schools ' +
    'libraries')
  
  animals_tagger = WSVKeywordTagger('Animals', 'animal animals dog dogs ' +
    'cat cats zoo bird birds zoos')
  
  health_tagger = WSVKeywordTagger('Health', 'health hospital hospitals ' +
    'medical healthcare mental hospice nursing cancer nurse nurses doctor ' +
    'doctors red+cross')
  
  seniors_tagger = WSVKeywordTagger('Seniors', 'senior seniors elderly')
  
  technology_tagger = WSVKeywordTagger('Technology', 'website computer ' +
    'computers technology web video graphic design')
  
  hph_tagger = WSVKeywordTagger('Poverty', 'habitat ' +
    'homeless hunger food housing poverty house poor')
  
  tutoring_tagger = WSVKeywordTagger('Tutoring', 'mentoring ' +
    'tutoring mentor counseling')
      
  # taggers is the list of Tagger subclass instances ot run each row through
  taggers = [nature_tagger, education_tagger, animals_tagger, health_tagger,
  seniors_tagger, technology_tagger, hph_tagger, tutoring_tagger]
  
  return taggers