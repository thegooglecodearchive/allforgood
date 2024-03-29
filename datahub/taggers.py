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
from datetime import datetime, date, time


import xml_helpers as xmlh
import re

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

  def do_tagging(self, rec, feedinfo, tag_count_dict, given_tags = []):
    """takes a record to be tagged, runs tagging functions"""
    scores = [f(rec, feedinfo) for f in self.tagging_functions]

    # get the average score from the tagging functions
    if len(scores) > 0:
      score = sum(scores) / len(scores)
    else:
      score = 0.0

    for tag in given_tags:
      rec.add_tag(tag)

    # add tag if the score, after all tagging functions, exceeds the threshold
    if score > self.score_threshold:
      rec.add_tag(self.tag_name)
      # and ppl asks us, "how many records were tagged X?"
      if not self.tag_name in tag_count_dict.keys():
        tag_count_dict.setdefault(self.tag_name, 1)
      else:
        tag_count_dict[self.tag_name] += 1

    return rec, tag_count_dict

class RegexTagger(Tagger):
  """RegexTagger is  a class for applying tagging based on matching a
  regex in the title or description of a listing. This can be expensive."""
  def __init__(self, tag_name, regex_dict):
    """Create relevant variables for the RegexTagger."""
    Tagger.__init__(self, tag_name)
    self.regex_dict = regex_dict
    self.examine_fields = ['title', 'description']

    self.score_threshold = 0.0 # right now, we'll tag if any keywords match
    self.tagging_functions.append(self.tag_by_regex)

  def tag_by_regex(self, rec, feedinfo):
    """Takes the regex defined in subclasses and checks them against
    the examined field, returning the average score."""
    score = 0.0
    for regex in self.regex_dict:
      rex = re.compile(regex)
      for field in self.examine_fields:
        search_match = rex.search(rec.get_val(field), re.I)
        if search_match is not None:
          score += self.regex_dict[regex]
    score /= len(self.regex_dict)
    return score

class DateRangeTagger(Tagger):
  """class for applying tagging based on date range"""
  def __init__(self, tag_name, month1, day1, month2, day2, omitted_providers = []):
    """Create relevant variables for the RegexTagger."""
    Tagger.__init__(self, tag_name)
    now = datetime.now()
    year1 = now.year
    if month2 < month1:
      year2 = year1 + 1
    else:
      year2 = year1
   
    year1 = now.year
    self.date_range_start = datetime(year1 , month1, day1)
    self.date_range_end = datetime(year2 , month2, day2)
    self.score_threshold = 0.0
    self.omitted_providers = omitted_providers
    self.tagging_functions.append(self.tag_by_date_range)

  def tag_by_date_range(self, rec, feedinfo):
    rtn = 0.0
    if xmlh.get_tag_val(feedinfo, "providerID") in self.omitted_providers:
      return 0.0

    str_start_date = rec.get_val("startDate")
    if len(str_start_date) > 0:
      try:
        start_date = datetime.strptime(str_start_date, "%m/%d/%Y")
      except:
        try:
          start_date = datetime.strptime(str_start_date, "%Y-%m-%d")
        except:
          start_date = None
      if start_date is not None and start_date >= self.date_range_start and start_date <= self.date_range_end:
        rtn = 1.0

    str_end_date = rec.get_val("endDate")
    if rtn < 1.0 and len(str_end_date) > 0:
      try:
        end_date = datetime.strptime(str_end_date, "%m/%d/%Y")
      except:
        try:
          end_date = datetime.strptime(end_date, "%Y-%m-%d")
        except:
          end_date = None
      if end_date is not None and end_date >= self.date_range_start and end_date <= self.date_range_end:
        rtn = 1.0

    return rtn


class FeedProviderIDTagger(Tagger):
  """class for applying tagging based on matching a
  regex on the feed providerName of a listing."""
  def __init__(self, tag_name, id_list):
    """Create relevant variables for the RegexTagger."""
    Tagger.__init__(self, tag_name)
    self.id_list = id_list
    self.score_threshold = 0.0 # tag if found
    self.tagging_functions.append(self.tag_by_source_id)

  def tag_by_source_id(self, rec, feedinfo):
    """matches the feed_providerID against the list of vetted IDs."""
    if xmlh.get_tag_val(feedinfo, "providerID") in self.id_list:
      return 1.0
    return 0.0

class SimpleRegexTagger(RegexTagger):
  """Class for tagging on a single regular expression."""
  def __init__(self, tag_name, regex):
    RegexTagger.__init__(self, tag_name, {regex:1.0})


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

  def tag_by_keywords(self, rec, feedinfo):
    """Takes the keywords defined in subclasses and checks them against
    the description, returning the average score."""
    score = 0.0
    for keyword in self.keywords:
      keyword_count = 0
      # Lowercase keyword and replace + with space for multiple word support
      # Ensure we require whitespace around the word or the start/end line
      keyword_find = re.compile('(^|\s)' + keyword.lower().replace('+', ' ')
                                + '($|\s)')
      for field in self.examine_fields:
        # Count the number of occurences of the modified keyword
        # in the value for this field
        keyword_match = keyword_find.search(rec.get_val(field), re.I)
      if keyword_match:
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
  mlk_date_tagger = DateRangeTagger('MLK', 1, 8, 1, 23, ['meetup'])
  mlk_tagger = WSVKeywordTagger('MLK', 'mlk' +
    ' martin+luther mlktech king+day' +
    ' day+on+not+a+day+off')

  oilspill_tagger = WSVKeywordTagger('OilSpill', 'oil+spill' +
    ' bp gulf+cleanup oil+cleanup spill+cleanup')

  earthday_tagger = WSVKeywordTagger('EarthDay', 'environment ' +
    ' nature environmental outdoors gardening garden park' +
    ' wetlands forest forests tree trees green trail trails' +
    ' sierra+club')

  mom_tagger = WSVKeywordTagger('Moms', 'mom' +
    ' mother family families kids children')

  hunger_tagger = WSVKeywordTagger('Hunger', 'anti-hunger' +
    ' breakfast childhood+hunger dinner feeding+america food food+bank' +
    ' food+pantry food+programs free+lunch healthy+meals hunger hungry' +
    ' hungry+children impoverished lunch meal+programs meals meals+on+wheels' +
    ' nutritious reduced+lunch school+lunches share+our+strength starvation' +
    ' starving underfed underprivileged thanksgiving soup+kitchen poverty' +
    ' poor nutrition frac malnourished foodbank dinner')

  nature_tagger = WSVKeywordTagger('Nature', 'environment nature ' +
    'environmental outdoors gardening garden park wetlands forest forests ' +
    'tree trees green trail trails sierra+club ')

  education_tagger = WSVKeywordTagger('Education', 'education reading ' +
    'teaching teacher teach books book library literacy school schools ' +
    'libraries')

  animals_tagger = WSVKeywordTagger('Animals', 'animal animals dog dogs ' +
    'cat cats zoo bird birds zoos puppies puppy kitten kitty critter ' +
    'critters frog frogs turtle turtles kittens')

  health_tagger = WSVKeywordTagger('Health', 'health hospital hospitals ' +
    'medical healthcare mental hospice nursing cancer nurse nurses doctor ' +
    'doctors red+cross')

  seniors_tagger = WSVKeywordTagger('Seniors', 'senior seniors elderly')

  technology_tagger = WSVKeywordTagger('Technology', 'website computer ' +
    'computers technology web video graphic design internet')

  hph_tagger = WSVKeywordTagger('Poverty', 'habitat ' +
    'homeless housing poverty house poor')

  tutoring_tagger = WSVKeywordTagger('Tutoring', 'mentoring ' +
    'tutoring mentor counseling')

  gardening_tagger = WSVKeywordTagger('Gardening', 'garden gardens ' +
    'gardener gardeners gardening')

  # skills-based matching
  lawyer_tagger = WSVKeywordTagger('Lawyer', 'lawyer lawyers ' +
    'attorney attorneys legal+counsel family+law court+system ' +
    'court+facilities court+forms legal+information legal+help')
  doctor_tagger = WSVKeywordTagger('Doctor', 'doctor doctors ' +
    'medical+professional medical+professionals nurse nurses')
  # sigh-- therapy also catches massage therapists, pet therapists,
  # physical therapists, etc.
  #psych_tagger = WSVKeywordTagger('Psych', 'therapist therapists ' +
  #  'psychologist psychologists psychiatrist psychiatrists')
  programmer_tagger = WSVKeywordTagger('Programmer', 'programmer ' +
    'programmers software+developer software+developers '+
    'software+engineer software+engineer')
  repairman_tagger = WSVKeywordTagger('Repairman', 'plumber plumbers ' +
    'electrician electricians carpenter carpenters bricklayer bricklayers '+
    'woodworker woodworkers')
  artist_tagger = WSVKeywordTagger('Artist', 'artist artists' +
    'drawing painter painters painting sculpting sculptor sculptors')
  graphicdesigner_tagger = WSVKeywordTagger('GraphicDesigner',
    'graphic+designer graphic+designers graphic+design graphic+skills '+
    'graphics+skills graphic+artist graphic+artists')
  videographer_tagger = WSVKeywordTagger('Videographer', 'videographer ' +
    'videographers video+editor')
  spanish_tagger = WSVKeywordTagger('SpanishSpeaker', 'spanish+speaking ' +
    'spanish+speaker bilingual+spanish reads+spanish writes+spanish')

  september11_tagger = SimpleRegexTagger('September11',
    '(9[\/\.]11|sep(t(\.|ember)?)?[ -]?(11|eleven)(th)?|' +
    'National Day of Service (and|&) Rememb(e)?rance)')

  veteransday_provider_tagger = FeedProviderIDTagger('VeteransDay', [
      '133' #servicenation
      ]) 
  veteransday_tagger = WSVKeywordTagger('VeteransDay', 'veteran veterans')

  vetted_tagger = FeedProviderIDTagger('Vetted', [
      #UGC '101', # usaservice (no longer active)
      '102', # handsonnetwork
      '500', # handsonnetwork
      '501', # handsonnetwork
      '502', # handsonnetwork
      '103', # idealist
      '104', # volunteermatch
      #UGC '105', # craigslist
      '106', # Americorps
      '107', # volunteergov
      #108 - unused / not live
      #109 - unused / not live
      #UGC '110', extraordinaries
      '111', # habitat
      #UGC '112', meetup
      #113 - unused / not live
      '114', # ServeNet.org
      '115', # americansolutions
      '117', # christiann volunteering
      '118', # volunteer2
      '119', # MENTOR (mentorpro)
      #UGC '120', myproj_servegov (serve.gov)
      '121', # seniorcorps
      '122', # unitedway
      '123', # americanredcross
      '124', # citizencorps/FEMA
      '125', # givingdupage
      '126', # ymca
      '127', # aarp
      '128', # greentheblock
      '129', # washoecounty
      '130', # universalgiving
      #UGC '131', 911dayofservice
      #'132', newyorkcares
      '134', #samaritan
      '141', #uso
      '142', #getinvolved
      #'1002', # girl scouts
      '1003', # united jewish communities
      '1004', # sierra club
      '1005', # 1Sky
      '1007', # Communities In Schools of Rockingham County
      '1023', # american cancer society
      '1049', # US Coast Guard Auxiliary
      '1050', # National Public Lands Day
      '1051', # Be Red Cross Ready
      '1053', # rappahannock united way
      '1055', # Jewish Big Brothers Big Sisters
      '1056', # American Red Cross
      '1063', # great non-profits
      '1143',  # cns.gov /dc
      #vetted but not live         Tech Mission
      ])

  # taggers is the list of Tagger subclass instances to run each row through
  # README: you also need to modify frontend/searchresult.py so your new
  # categories are displayed in the consumer UI next to each result.
  taggers = [
    # vetted/UGC
    vetted_tagger,
    # topics
    #earthday_tagger,
    #mlk_tagger, mlk_date_tagger,
    #mom_tagger,
    #hunger_tagger,
    #nature_tagger, education_tagger, animals_tagger, health_tagger,
    ##seniors_tagger, technology_tagger, hph_tagger, tutoring_tagger,
    #gardening_tagger,
    # skills
    #artist_tagger, lawyer_tagger, doctor_tagger, programmer_tagger,
    #repairman_tagger, videographer_tagger, graphicdesigner_tagger,
    #oilspill_tagger,
    #spanish_tagger,
    #veteransday_provider_tagger,
    #veteransday_tagger,
    # special events
    #september11_tagger
    ]

  return taggers
