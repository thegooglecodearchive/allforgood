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
class to represent search results.
"""

import re
import urlparse
import datetime
import time
import hashlib
import logging

from xml.sax.saxutils import escape

from fastpageviews import pagecount
import models
import modelutils
import utils

def get_rfc2822_datetime(when = None):
  """GAE server localtime appears to be UTC and timezone %Z
  is an empty string so to satisfy RFC date format
  requirements in output=rss we append the offset in hours
  from UTC for our local time (now, UTC) i.e. +0000 hours
  ref: http://feedvalidator.org/docs/error/InvalidRFC2822Date.html
  ref: http://www.feedvalidator.org to check feed validity
  eg, Tue, 10 Feb 2009 17:04:28 +0000"""
  if not when:
    when = time.gmtime()
  return time.strftime("%a, %d %b %Y %H:%M:%S", when) + " +0000"

def js_escape(string):
  """quote characters appropriately for javascript.
  TODO: This escape method is overly agressive and is messing some snippets
  up.  We only need to escape single and double quotes."""
  return re.escape(string)

class SearchResult(object):
  """class to hold the results of a search to the backend."""
  def __init__(self, url, title, snippet, location, item_id, base_url):
    # TODO: HACK: workaround for issue 404-- broken servegov links
    # hack added here so the urlsig's come out correctly and the fix
    # applies everywhere including xml_url, API calls, etc.
    url = re.sub(
      # regexp written to be very specific to myproject.serve.gov
      # and myproject.nationalservice.gov (aka mlk_day), and not
      # break once the feed changes
      r'(myproject[.].+?[.]gov.+?)subProjectId', r'\1&subProjectId', url)
    
    # TODO: Consider using kwargs or something to make this more generic.
    self.url = url
    self.url_sig = None
    self.title = title
    self.snippet = snippet
    self.location = location
    self.item_id = item_id
    self.base_url = base_url
    # app engine does not currently support the escapejs filter in templates
    # so we have to do it our selves for now
    self.js_escaped_title = js_escape(title)
    self.js_escaped_snippet = js_escape(snippet)
    # TODO: find out why this is not unique
    # hack to avoid guid duplicates
    self.xml_url = escape(url) + "#" + self.item_id
    parsed_url = urlparse.urlparse(url)
    self.url_short = parsed_url.netloc
    if url.find("volunteer.gov/gov") >= 0:
      # hack for volunteer.gov/gov, which is different from
      # volunteer.gov/ (which redirects to serve.net)
      self.url_short += "/gov"
    self.host_website = parsed_url.netloc
    if self.host_website.startswith("www."):
      self.host_website = self.host_website[4:]
    # user's expressed interest
    self.interest = None
    # stats from other users.
    self.interest_count = 0
    # TODO: implement quality score
    self.quality_score = 0.1
    self.impressions = 0
    self.pubdate = get_rfc2822_datetime()
    self.score = 0.0
    self.score_notes = ""
    self.score_str = ""

  def set_score(self, score, notes):
    """assign score value-- TODO: consider moving scoring code to this class."""
    self.score = score
    self.score_notes = notes
    self.score_str = "%.4g" % (score)

def compare_result_dates(dt1, dt2):
  """private helper function for dedup()"""
  if (dt1.t_startdate > dt2.t_startdate):
    return 1
  elif (dt1.t_startdate < dt2.t_startdate):
    return -1
  else:
    return 0

class SearchResultSet(object):
  """Contains a list of SearchResult objects.

  Attributes:
    results: List of SearchResults.  Required during initialization.
    merged_results: This is populated after a call to dedup().  It will
      contain the original results, after merging of duplicate entries.
    clipped_results: This is populated after a call to clip_merged_results.
      It will contain the merged_results, clamped to a start-index and
      max-length (the 'start' and 'num' query parameters).
    query_url_encoded: URL query used to retrieve data from backend.
      For debugging.
    query_url_unencoded: urllib.unquote'd version of the above.
    num_merged_results: Number of merged results after a dedup()
      operation.  Used by Django.
    estimated_merged_results: estimated number of total results accounting
      for merging, given result_set.estimated_backend_results
  """
  def __init__(self, query_url_unencoded, query_url_encoded, results):
    self.query_url_unencoded = query_url_unencoded
    self.query_url_encoded = escape(query_url_encoded)
    self.results = results
    self.num_results = 0
    self.estimated_results = 0
    self.num_merged_results = 0
    self.merged_results = []
    self.clipped_results = []
    self.clip_start_index = 0  # Index at which clipped_results begins.
    self.has_more_results = False  # After clipping, are there more results?
    self.estimated_merged_results = 0
    self.pubdate = get_rfc2822_datetime()
    self.last_build_date = self.pubdate

  def append_results(self, results):
    """append a results arry to this results set and rerun dedup()"""
    self.num_results = len(self.results) + len(results.results)
    self.results.extend(results.results)
    self.merged_results = []
    self.clipped_results = []
    self.dedup()

  def clip_set(self, start, num, result_set):
    """Extract just the slice of merged results from start to start+num.
    No need for bounds-checking -- python list slicing does that
    automatically.  Indexed from 1."""
    start -= 1  # Adjust to zero indexing.
    self.clipped_results = result_set[start:start + num]
    self.clip_start_index = start
    if self.estimated_merged_results > start + num:
      self.has_more_results = True

  def clip_merged_results(self, start, num):
    """clip to start/num using the merged results."""
    logging.debug("clip_merged_results: start=%d  num=%d  has_more=%s "
                  "(merged len = %d)" %
                  (start, num, str(self.has_more_results),
                   len(self.merged_results)))
    return self.clip_set(start, num, self.merged_results)

  def clip_results(self, start, num):
    """clip to start/num using the unmerged (original) results."""
    return self.clip_set(start, num, self.results)

  def track_views(self, num_to_incr=1):
    """increment impression counts for items in the set."""
    logging.debug(str(datetime.datetime.now())+" track_views: start")
    for primary_res in self.clipped_results:
      #logging.debug("track_views: key="+primary_res.merge_key)
      primary_res.merged_impressions = pagecount.IncrPageCount(
        pagecount.VIEWS_PREFIX+primary_res.merge_key, num_to_incr)
      # TODO: for now (performance), only track merge_keys, not individual items
      #primary_res.impressions = pagecount.IncrPageCount(primary_res.item_id, 1)
      #for res in primary_res.merged_list:
      #  res.impressions = pagecount.IncrPageCount(res.item_id, 1)
    logging.debug(str(datetime.datetime.now())+" track_views: end")

  def dedup(self):
    """modify in place, merged by title and snippet."""

    def safe_str(instr):
      """private helper function for dedup()"""
      return_val = ""
      try:
        return_val = str(instr)
      except ValueError:
        for inchar in instr:
          try:
            safe_char = str(inchar)
            return_val += safe_char
          except ValueError:
            continue # discard
      return return_val

    def assign_merge_keys():
      """private helper function for dedup()"""
      for res in self.results:
        # Merge keys are M + md5hash(some stuff). This distinguishes them from
        # the stable IDs, which are just md5hash(someotherstuff).
        res.merge_key = 'M' + hashlib.md5(safe_str(res.title) +
                                          safe_str(res.snippet) +
                                          safe_str(res.location)).hexdigest()
        res.url_sig = utils.signature(res.url + res.merge_key)
        # we will be sorting & de-duping the merged results
        # by start date so we need an epoch time
        res.t_startdate = res.startdate.timetuple()
        # month_day used by django
        res.month_day = (time.strftime("%B", res.t_startdate) + " " +
                         str(int(time.strftime("%d", res.t_startdate))))
        # this is for the list of any results merged with this one
        res.merged_list = []
        res.merged_debug = []

    def merge_result(res):
      """private helper function for dedup()"""
      merged = False
      for i, primary_result in enumerate(self.merged_results):
        if primary_result.merge_key == res.merge_key:
          # merge it
          listed = False
          for merged_result in self.merged_results[i].merged_list:
            # do we already have this date + url?
            if (merged_result.t_startdate == self.merged_results[i].t_startdate
                and merged_result.url == self.merged_results[i].url):
              listed = True
              break
          if not listed:
            self.merged_results[i].merged_list.append(res)
            self.merged_results[i].merged_debug.append(res.location + ":" +
                res.startdate.strftime("%Y-%m-%d"))
          merged = True
          break
      if not merged:
        self.merged_results.append(res)

    def compute_more_less():
      """Now we are making something for the django template to display
      for the merged list we only show the unique locations and dates
      but we also use the url if it is unique too
      for more than 2 extras we will offer "more" and "less"
      we will be showing the unique dates as "Month Date"."""
      for i, res in enumerate(self.merged_results):
        res.idx = i + 1
        if len(res.merged_list) > 1:
          res.merged_list.sort(cmp=compare_result_dates)
          location_was = res.location
          res.less_list = []
          if len(res.merged_list) > 2:
            more_id = "more_" + str(res.idx)
            res.more_id = more_id
            res.more_list = []

          more = 0
          res.have_more = True
          for merged_result in res.merged_list:
            def make_linkable(text, merged_result, res):
              """generate HTML hyperlink for text if merged_result != res."""
              if merged_result.url != res.url:
                return '<a href="' + merged_result.url + '">' + text + '</a>'
              else:
                return text

            entry = ""
            if merged_result.location != location_was:
              location_was = merged_result.location
              entry += ('<br/>'
               + make_linkable(merged_result.location, merged_result, res)
               + ' on ')
            elif more > 0:
              entry += ', '

            entry += make_linkable(merged_result.month_day, merged_result, res)
            if more < 3:
              res.less_list.append(entry)
            else:
              res.more_list.append(entry)

            more += 1

    def remove_blacklisted_results():
      """Private helper function for dedup().

      Looks up stats for each result and deletes blacklisted results."""
      opp_ids = [result.merge_key for result in self.results]
      opp_stats = modelutils.get_by_ids(models.VolunteerOpportunityStats, 
                                        opp_ids)
      unknown_keys = set()
      nonblacklisted_results = []

      for result in self.results:
        if result.merge_key not in opp_stats:
          unknown_keys.add(result.merge_key)
          nonblacklisted_results.append(result)
        elif not opp_stats[result.merge_key].blacklisted:
          nonblacklisted_results.append(result)

      self.results = nonblacklisted_results
      if unknown_keys:
        # This probably shouldn't be done right here... but we'll stuff these
        # in the memcache to prevent future datastore lookups.
        logging.debug('Found unblacklisted items which had no memcache or ' +
                      'datastore entries. Adding to memcache. Items: %s', 
                      unknown_keys)
        models.VolunteerOpportunityStats.add_default_entities_to_memcache(
            unknown_keys)

    # dedup() main code
    assign_merge_keys()
    remove_blacklisted_results()
    for res in self.results:
      merge_result(res)
    compute_more_less()

    self.num_merged_results = len(self.merged_results)
    if len(self.results) == 0:
      self.estimated_merged_results = self.estimated_results
    else:
      self.estimated_merged_results = int(self.estimated_results *
          self.num_merged_results / len(self.results))