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
Test for query rewriter
"""

import re
import unittest
import query_rewriter

class TestQueryRewriter(unittest.TestCase):
  """ Unittests on QueryRewriter """
  def setUp(self):
    """ Override by setting some shared constants """
    # Strings
    self.nature = 'nature'
    self.nature_rewrite = 'category:' + self.nature
    self.sept = "sept"
    self.sept_rewrite = 'category:' + self.sept
    self.match_query = self.nature + ' ' + self.sept +' student dog wash in'
    # Rewriters
    self.nature_rewriter = query_rewriter.KeywordRewriter(self.nature,
                                                          self.nature_rewrite)
    self.september11_rewriter = query_rewriter.RegexRewriter(self.sept,
                                                             self.sept_rewrite)
    self.both_rewriters = query_rewriter.QueryRewriter()
    self.both_rewriters.add_rewriters([self.nature_rewriter,
                                       self.september11_rewriter])

  def test_add_rewriter(self):
    """ Assert that adding rewriters works correctly """
    rewriters = query_rewriter.QueryRewriter()
    assert len(rewriters.rewrite_functions) == 0
    rewriters.add_rewriters([self.nature_rewriter])
    assert len(rewriters.rewrite_functions) == 1
    rewriters.add_rewriters([self.nature_rewriter,
                             self.september11_rewriter,
                             self.september11_rewriter])
    assert len(rewriters.rewrite_functions) == 4

  def test_regex_rewriter(self):
    """ Assert regex rewriter works as expected """
    rewritten_match_query = self.september11_rewriter.rewrite_query(
        self.match_query)
    self.assertNotEqual(self.match_query, rewritten_match_query)
    # Matches and adds only the september 11 category
    assert self.__rewritten(self.match_query, rewritten_match_query)
    assert not self.__nature_rewritten(rewritten_match_query)
    assert self.__sept_rewritten(rewritten_match_query)
    self.assertEqual(
        rewritten_match_query,
        self.september11_rewriter.rewrite_using_regexp(self.match_query))

  def test_keyword_rewriter(self):
    """ Assert keyword rewriter works as expected """
    rewritten_match_query = self.nature_rewriter.rewrite_query(self.match_query)
    self.assertNotEqual(self.match_query, rewritten_match_query)
    # Matches and adds only the nature category
    assert self.__rewritten(self.match_query, rewritten_match_query)
    assert self.__nature_rewritten(rewritten_match_query)
    assert not self.__sept_rewritten(rewritten_match_query)
    self.assertEqual(rewritten_match_query,
                     self.nature_rewriter.keyword_rewrite(self.match_query))

  def test_get_rewriters(self):
    """Assert set has rewriters and edits matching query"""
    rewriters = query_rewriter.get_rewriters()
    assert rewriters is not None
    assert len(rewriters.rewrite_functions) > 0

  def test_rewrite_query(self):
    """ Assert rewrite query works as expected """
    # Test matches both
    rewritten_match_query = self.both_rewriters.rewrite_query(self.match_query)
    assert self.__rewritten(self.match_query, rewritten_match_query)
    assert self.__nature_rewritten(rewritten_match_query)
    assert self.__sept_rewritten(rewritten_match_query)
    # Test no match
    non_match_query = 'student dog wash in peace'
    rewritten_non_match_query = self.both_rewriters.rewrite_query(
        non_match_query)
    assert not self.__rewritten(non_match_query, rewritten_non_match_query)
    assert not self.__nature_rewritten(rewritten_non_match_query)
    assert not self.__sept_rewritten(rewritten_non_match_query)

  def __nature_rewritten(self, query):
    """Helper function to check if nature rewrite"""
    assert query.find(self.nature_rewrite) is not None
    return query.find(self.nature_rewrite) != -1

  def __sept_rewritten(self, query):
    """Helper function to check if sept rewrite"""
    assert query.find(self.sept_rewrite) is not None
    return query.find(self.sept_rewrite) != -1


  def __rewritten(self, original, new):
    """Helper function to check if any changes were made with a rewrite"""
    # Contains original
    assert new.find(original) != -1
    # If changed,should include 'OR'
    if new != original:
      assert new.find("OR", re.I) != -1
    return new != original


if __name__ == "__main__":
  unittest.main()
