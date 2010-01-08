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
Routines for modifying search queries for overrides and the like.
"""

import re
import logging

class QueryRewriter(object):
  """Base class for all QueryRewriters. """
  def __init__(self):
    self.rewrite_functions = []

  def add_rewriters(self, rewriter_list):
    """adds a rewriter's functions to the list of functions to run"""
    if rewriter_list:
      for rewriter in rewriter_list:
        for rewrite in rewriter.rewrite_functions:
          self.rewrite_functions.append(rewrite)

  def rewrite_query(self, query):
    """takes a query to be rewritten, runs rewriter functions against it"""
    for function in self.rewrite_functions:
      query = function(query)
    return query

class RegexRewriter(QueryRewriter):
  """If query matches regex, OR the query with additional parameters"""
  def __init__(self, regex, param):
    QueryRewriter.__init__(self)
    self.regex = regex
    self.param = param
    self.rewrite_functions.append(self.rewrite_using_regexp)

  def rewrite_using_regexp(self, query):
    """if part of query matches the regexp, add param to query"""
    updated_query = query
    logging.info("Regexp rewrite query: " + query)

    search_match =  re.search(self.regex, query, re.I)
    if search_match:
      updated_query = self.param + " OR " + query
    return updated_query


class KeywordRewriter(QueryRewriter):
  """If a query contains any of the given keywords, OR query with parameters"""
  def __init__(self, keywords_list, param):
    QueryRewriter.__init__(self)
    self.keywords = keywords_list.split()
    self.param = param
    self.rewrite_functions.append(self.keyword_rewrite)

  def keyword_rewrite(self, query):
    """if part of query matches any keyword, add param to query"""
    matches = False
    updated_query = query
    for keyword in self.keywords:
      if re.search('(^|\W)' + keyword.lower().replace('+', ' ') + '($|\W)',
                   query, re.I):
        matches = True
    if matches:
      updated_query = self.param + " OR " + query
    return updated_query


# Create basic query overrides
def get_rewriters():
  """returns the current rewriterer instances we're using"""
  # Topics
  mlk_rewriter = KeywordRewriter('mlk martin+luther', 'category:MLK')

  hunger_rewriter = KeywordRewriter('anti-hunger' +
    ' breakfast childhood+hunger dinner feeding+america food food+bank' +
    ' food+pantry food+programs free+lunch healthy+meals hunger hungry' +
    ' hungry+children impoverished lunch meal+programs meals meals+on+wheels' +
    ' nutritious reduced+lunch school+lunches share+our+strength starvation' +
    ' starving underfed underprivileged thanksgiving soup+kitchen poverty' +
    ' poor nutrition frac malnourished foodbank', 'category:Hunger')

  nature_rewriter = KeywordRewriter('environment nature ' +
    'environmental outdoors gardening garden park wetlands forest forests ' +
    'tree trees green trail trails sierra+club', 'category:nature')

  education_rewriter = KeywordRewriter('education reading ' +
    'teaching teacher teach books book library literacy school schools ' +
    'libraries', 'category:education')

  animals_rewriter = KeywordRewriter('animal animals dog dogs ' +
    'cat cats zoo bird birds zoos puppies puppy kitten kitty critter ' +
    'critters frog frogs turtle turtles kittens', 'category:animals')

  health_rewriter = KeywordRewriter('health hospital hospitals ' +
    'medical healthcare mental hospice nursing cancer nurse nurses doctor ' +
    'doctors red+cross', 'category:health')

  seniors_rewriter = KeywordRewriter('senior seniors elderly',
    'category:seniors')

  technology_rewriter = KeywordRewriter('website computer ' +
    'computers technology web video graphic design internet',
    'category:technology')

  hph_rewriter = KeywordRewriter('habitat ' +
    'homeless housing poverty house poor', 'category:poverty')

  tutoring_rewriter = KeywordRewriter('mentoring ' +
    'tutoring mentor counseling', 'category:tutoring')

  gardening_rewriter = KeywordRewriter('garden gardens ' +
    'gardener gardeners gardening', 'category:gardening')

  # Skills
  lawyer_rewriter = KeywordRewriter('lawyer lawyers ' +
    'attorney attorneys legal+counsel family+law court+system ' +
    'court+facilities court+forms legal+information legal+help',
    'category:lawyer')

  doctor_rewriter = KeywordRewriter('doctor doctors ' +
    'medical+professional medical+professionals nurse nurses',
    'category:doctor')
  # sigh-- therapy also catches massage therapists, pet therapists,
  # physical therapists, etc.

  #psych_rewriter = KeywordRewriter('therapist therapists ' +
  #  'psychologist psychologists psychiatrist psychiatrists', 'category:pysch')

  programmer_rewriter = KeywordRewriter('programmer ' +
    'programmers software+developer software+developers '+
    'software+engineer software+engineer', 'category:programmer')

  repairman_rewriter = KeywordRewriter('plumber plumbers ' +
    'electrician electricians carpenter carpenters bricklayer bricklayers '+
    'woodworker woodworkers', 'category:repairman')

  artist_rewriter = KeywordRewriter('artist artists' +
    'drawing painter painters painting sculpting sculptor sculptors',
    'category:artist')

  graphicdesigner_rewriter = KeywordRewriter(
    'graphic+designer graphic+designers graphic+design graphic+skills '+
    'graphics+skills graphic+artist graphic+artists',
    'category:graphicdesigner')

  videographer_rewriter = KeywordRewriter('videographer ' +
    'videographers video+editor', 'category:videographer')

  spanish_rewriter = KeywordRewriter('spanish+speaking ' +
    'spanish+speaker bilingual+spanish reads+spanish writes+spanish',
    'category:spanishspeaker')

  # Events
  september11_rewriter = RegexRewriter(
    '(9[\/\.]11|sep(t(\.|ember)?)?[ -]?(11|eleven)(th)?|' +
    'National Day of Service (and|&) Rememb(e)?rance)', 'category:September11')

  # Vetted?

  rewriters = QueryRewriter()
  rewriters.add_rewriters([
      # topics
      hunger_rewriter,
      nature_rewriter,
      education_rewriter,
      animals_rewriter,
      health_rewriter,
      seniors_rewriter,
      technology_rewriter,
      hph_rewriter,
      tutoring_rewriter,
      gardening_rewriter,
      # skills
      artist_rewriter,
      lawyer_rewriter,
      doctor_rewriter,
      programmer_rewriter,
      repairman_rewriter,
      videographer_rewriter,
      graphicdesigner_rewriter,
      spanish_rewriter,
      # special events
      #september11_rewriter
      ])

  return rewriters
