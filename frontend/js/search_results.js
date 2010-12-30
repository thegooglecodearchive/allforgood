/* Copyright 2009 Google Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

var map;
var NUM_PER_PAGE = 10;
var searchResults = [];

/** Query params for backend search, based on frontend parameters.
 *
 * @constructor
 * @param {string} keywords Search keywords.
 * @param {string|GLatLng} location Location in either string form (address) or
 *      a GLatLng object.
 * @param {number} start The start index for results.  Must be integer.
 * @param {string} opt_timePeriod The time period.
 * @param {Object} opt_filters Filters for this query.
 *      Maps 'filtername':value.
 */
function Query(keywords, location, pageNum, useCache, opt_timePeriod,
               opt_filters) {
  var me = this;
  me.keywords_ = keywords;
  me.location_ = location;
  me.pageNum_ = pageNum;
  me.use_cache_ = useCache;
  me.timePeriod_ = opt_timePeriod || 'everything';
  me.filters_ = opt_filters || {};
};

Query.prototype.clone = function() {
  var me = this;
  return jQuery.extend(true, new Query(), me);
};

/** Updates the location.hash with the given query, which then
 * triggers the search.
 */
Query.prototype.execute = function() {
  var urlQueryString = this.getUrlQuery();
  // Set the URL hash, but only if the query string is not empty.
  // Setting hash to an empty string causes a page reload.
  if (urlQueryString.length > 0 && urlQueryString != window.location.hash) {
    dhtmlHistory.add(urlQueryString);
    // Sleep to give the add function a chance to manipulate the hash.
    // TODO(manzoid): Revisit.  RSH says these delays are necessary, but
    // should independently verify why.
    // See comment on lines 191-3 of rsh.js.
    setTimeout(executeSearchFromHashParams, dhtmlHistory.getWaitTime() + 1);
  }
};

Query.prototype.setPageNum = function(pageNum) {
  this.pageNum_ = pageNum;
};

Query.prototype.getPageNum = function() {
  return this.pageNum_;
};

Query.prototype.getKeywords = function() {
  return this.keywords_;
};

Query.prototype.setKeywords = function(keywords) {
  this.keywords_ = keywords;
};

Query.prototype.getLocation = function() {
  return this.location_;
};

Query.prototype.setLocation = function(location) {
  this.location_ = location;
};

Query.prototype.getTimePeriod = function() {
  return this.timePeriod_;
};

Query.prototype.setTimePeriod = function(period) {
  this.timePeriod_ = period;
};

Query.prototype.getFilter = function(name) {
  if (name in this.filters_) {
    return this.filters_[name];
  } else {
    return undefined;
  }
}

Query.prototype.setFilter = function(name, value) {
  this.filters_[name] = value;
}

Query.prototype.getUrlQuery = function() {
  var me = this;
  urlQuery = '';
  function addQueryParam(name, value) {
    if (urlQuery.length > 0) {
      urlQuery += '&';
    }
    urlQuery += name + '=' + escape(value);
  }

  // Keyword search
  var keywords = me.getKeywords();
  if (keywords && keywords.length > 0) {
    addQueryParam('q', keywords);
  }

  // Pagination
  addQueryParam('num', NUM_PER_PAGE)
  addQueryParam('start', me.getPageNum() * NUM_PER_PAGE + 1);  // 1-indexed.

  // Location
  var location = me.getLocation();
  if (location && location.length > 0) {
    addQueryParam('vol_loc', location);
  }

  // Time period
  var period = me.getTimePeriod();
  if (period) {
    addQueryParam('timeperiod', period)
  }

  // Add additional filters to query URL.
  for (var name in me.filters_) {
    var value = me.getFilter(name);
    if (value) {
      addQueryParam(name, value);
    }
  }

  // Use Cache
  var use_cache = me.getUseCache();
  addQueryParam('cache', use_cache);

  return urlQuery;
};

Query.prototype.getUseCache = function() {
  return this.use_cache_;
};

Query.prototype.setUseCache = function(use_cache) {
  this.use_cache_ = use_cache;
};


function createQueryFromUrlParams() {
  var keywords = getHashParam('q', '');

  var location = getHashParam('vol_loc',
      getDefaultLocation().displayLong);

  var start = Number(getHashParam('start', '1'));
  start = Math.max(start, 1);

  var numPerPage = Number(getHashParam('num', NUM_PER_PAGE));
  numPerPage = Math.max(numPerPage, 1);

  var pageNum = (start - 1) / numPerPage;

  var timePeriod = getHashParam('timeperiod');

  var filters = {};

  // Read in the other filters from the URL, and place them in
  // 'filters' object.
  function getNamedFilterFromUrl(name) {
    filters[name] = getHashParam(name, '');
  }
  getNamedFilterFromUrl('who_filter');
  getNamedFilterFromUrl('activity_filter');

  // mt: add new params here
  getNamedFilterFromUrl('bf');
  getNamedFilterFromUrl('bft');
  getNamedFilterFromUrl('vol_dist');
  getNamedFilterFromUrl('vol_startdate');
  getNamedFilterFromUrl('vol_enddate');
  getNamedFilterFromUrl('key');

  var use_cache = Number(getHashParam('cache', '1'));

  return new Query(keywords, location, pageNum, use_cache, timePeriod, filters);
}

/**
 * @constructor
 */
function FilterWidget(div, title, entries, initialValue, callback) {
  var me = this;

  me.div_ = div;
  me.title_ = title;
  me.entries_ = entries;
  me.value_ = initialValue;
  me.callback_ = callback;

  me.render();
}

FilterWidget.prototype.render = function() {
  var me = this;
  var titleDiv = document.createElement('div');
  titleDiv.innerHTML = me.title_;
  titleDiv.className = 'filterwidget_title';
  me.div_.innerHTML = '';
  me.div_.appendChild(titleDiv);

  var clickCallback = function(index) {
    return function() {
      var newValue = me.entries_[index][1];
      me.setValue(newValue);
      me.callback_(newValue);
    };
  }

  for (var i = 0; i < me.entries_.length; i++) {
    var entryDiv = document.createElement('div');
    entryDiv.className = 'filterwidget_entry';
    me.div_.appendChild(entryDiv);

    if (me.entries_[i][1] == me.value_) {
      entryDiv.innerHTML = '<b>' + me.entries_[i][0] + '</b>';
    } else {
      var link = document.createElement('a');
      link.innerHTML = me.entries_[i][0];
      link.href = 'javascript:void(0)';
      link.onclick = clickCallback(i);
      entryDiv.appendChild(link);
    }
  }
};

FilterWidget.prototype.getValue = function() {
  return this.value_;
};

FilterWidget.prototype.setValue = function(newValue) {
  var me = this;
  me.value_ = newValue;
  me.render();
};

/** Perform a search using the current URL parameters and IP geolocation.
 */
function onLoadSearch() {
  if (el('when_filter_widget')) {
    whenFilterWidget =
        new FilterWidget(el('when_filter_widget'),
                         'When',
                         [ ['Anytime', 'everything'],
                           ['Today', 'today'],
                           ['This weekend', 'this_weekend'],
                           ['This week', 'this_week'],
                           ['This month', 'this_month'] ],
                         'everything',
                         function(value) { submitForm('when_widget'); });
  }

  if (el('location')) {
    setInputFieldValue(el('location'), getDefaultLocation().displayLong);
  }

  // Using jquery json functions where RSH expects other json functions,
  // pass in as overrides.
  dhtmlHistory.create({
      debugMode: false, // Set to 'true' to see the hidden form & iframe.
      toJSON: function(o) {
        return $.toJSON(o);
      },
      fromJSON: function(s) {
        return $.evalJSON(s);
      }
  });
  dhtmlHistory.initialize();
  dhtmlHistory.addListener(executeSearchFromHashParams);

  createQueryFromUrlParams().execute();

  try {
    el('more').style.display = '';
  } catch(err) {
  }
}

/** Asynchronously execute a search based on the current parameters.
 */
executeSearchFromHashParams = function(currentLocation) {
  /** The XMLHttpRequest of the current search, kept so it can be cancelled.
   * @type {XMLHttpRequest}
   */
  var currentXhr;

  return function(currentLocation) {
    // Try to avoid the annoyance of a useless extra click on Back button.
    // TODO(timman): Find a cleaner way to determine first-rewrite.
    if (typeof currentLocation == 'string') {
      // Duck-type our programmatically expanded (rewritten) query string.
      if (currentLocation.indexOf('timeperiod') == -1 &&
          currentLocation.indexOf('num=') == -1) {
        // We have identified this location as being a fragmentary initial
        // location such as "q=Education&vol_loc=90815", so we skip past it.
        window.history.go(-1);
      }
    }

    // abort any currently running query
    if (currentXhr) {
      currentXhr.abort();
    }

    var query = createQueryFromUrlParams();
    el('loading').style.display = '';
    if(el('loading-bottom')){
      el('loading-bottom').style.display = '';
    }
    // TODO: eliminate the need for lastSearchQuery to be global

    lastSearchQuery = query;

    var success = function(text, status) {
      setInputFieldValue(el('keywords'), query.getKeywords());
      if (whenFilterWidget) {
        whenFilterWidget.setValue(query.getTimePeriod());
      }
      var regexp = new RegExp('[a-zA-Z]')
      if (regexp.exec(query.getLocation())) {
        // Update location field in UI, but only if location text isn't
        // just a latlon geocode.
        if (el('location')) {
          setInputFieldValue(el('location'), query.getLocation());
        }
      }
      jQuery('#snippets_pane').html(text);
      asyncLoadManager.addCallback('map', function() {
        map.autoZoomAndCenter(query.getLocation());
      });
      el('loading').style.display = 'none';
      if(el('loading-bottom')){
        el('loading-bottom').style.display = 'none';
      }
      // Load analytics, done here to ensure search is finished first
      // Only loading for search result pages here and loaded in
      // homepage.js for the hp and in base.html for static pages
      loadGA();
    };

    var error = function (XMLHttpRequest, textStatus, errorThrown) {
      // TODO: handle error
    };

    /* UI snippets URL.  We don't use '/api/search?' because the UI output
       contains application-specific formatting and inline JS, and has
       user-specific info. */
    var url;
    if (currentPageName == 'SEARCH') {
      if (typeof campaignId != 'undefined' ) {
        url = '/ui_snippets?campaign_id=' + campaignId + '&'
      }
      else {
        url = '/ui_snippets?';
      }
    } else if (currentPageName == 'MY_EVENTS') {
      url = '/ui_my_snippets?';
    }

    url += query.getUrlQuery();

    var location = query.getLocation();
    if (!location || location.length == 0) {
      // TODO: Make these the defaults inside search.py/base_search.py.
      //       Will then need to test that "No Results" message doesn't
      //       show "USA".
      url += '&vol_loc=USA&vol_dist=1500';
    }

    var referrer = document.referrer;
    if (referrer) {
      url += '&referrer=' + encodeURIComponent(referrer);
    }

    currentXhr = jQuery.ajax({
      url: url,
      async: true,
      dataType: 'html',
      error: error,
      success: success
    });
  };
}(); // executed inline to close over the 'currentXhr' variable.


/** Called from the "Refine" button's onclick, the main form onsubmit,
 * and the time period filter.
 * @param {string} invoker Who invoked this submission?  One of
 *                         ['keywords', 'when_widget', 'map'].
 */
function submitForm(invoker) {
  var keywords = getInputFieldValue(el('keywords'));

  // If the keywords search form is invoked from non-search page,
  // redirect to search page.
  if (invoker == 'keywords' && currentPageName != 'SEARCH') {
    // TODO: Incorporate current 'when' filter?
    window.location = '/search#q=' + keywords;
    return;
  }

  var location = getInputFieldValue(el('location'));

  if (invoker == 'map') {
    setSessionCookie('user_vol_loc', location);
  }

  var timePeriod = whenFilterWidget.getValue();

  // TODO: strip leading/trailing whitespace.

  if (location == '') {
    location = getDefaultLocation().displayLong;
  }

  var query = lastSearchQuery.clone();
  query.setKeywords(keywords);
  query.setLocation(location);
  query.setPageNum(0);
  query.setTimePeriod(timePeriod);

  query.execute();
}

function setWhoFilter(value) {
  var query = lastSearchQuery.clone();
  query.setFilter('who_filter', value);
  query.execute();
}

/** Called from the onclick in the "more" prompt of a snippet
 *
 * @param {string} id the element id of the "more", "less" div's
 *
 */
function showMoreDuplicates(id) {
  var it = document.getElementById(id);
  if (it) {
    it.style.display = 'inline';
  }
  it = document.getElementById('s' + id);
  if (it) {
    it.style.display = 'none';
  }
}

/** Called from the onclick in the "less" prompt of a snippet
 *
 * @param {string} id the element id of the "more", "less" div's
 *
 */
function showLessDuplicates(id) {
  var it = document.getElementById(id);
  if (it) {
    it.style.display = 'none';
  }
  it = document.getElementById('s' + id);
  if (it) {
    it.style.display = 'inline';
  }
}

function goToPage(pageNum) {
  if (pageNum < 0) {
    return;
  }
  if (lastSearchQuery) {
    // Change page number, and re-do the last search.
    lastSearchQuery.setPageNum(pageNum);
    lastSearchQuery.execute();
  }
}

function categorySearch(category) {
  if (category == '') {
    return;
  }
  if (lastSearchQuery) {
    // Change query, and re-do the last search.
    lastSearchQuery.setKeywords("category:"+category);
    lastSearchQuery.execute();
  }
}

function renderPaginator(div, totalNum, forceShowNextLink) {
  if (!lastSearchQuery || searchResults.length == 0 || totalNum == 0) {
    return;
  }

  var numPages = parseInt(Math.ceil(totalNum / NUM_PER_PAGE));
  if (numPages == 1 && !forceShowNextLink) {
    return;
  }
  if (numPages > 20) {
    numPages = 20;
  }

  var html = [];

  function renderLink(pageNum, text) {
    html.push('<a href="javascript:goToPage(', pageNum, ');void(0);">',
        text, '</a> ');
  }

  var currentPageNum = lastSearchQuery.getPageNum();
  if (currentPageNum > 0) {
    renderLink(currentPageNum - 1, '&laquo; Previous Page');
  }

  /* TODO: re-add once pagination is reasonably accurate
  if (numPages > 1) {
    for (var i = 0; i < numPages; i++) {
      if (i == currentPageNum) {
        html.push('' + (i+1) + ' ');
      } else {
        renderLink(i, i+1);
      }
    }
  }
  */

  if (currentPageNum != numPages - 1 || forceShowNextLink) {
    html.push('&nbsp;&nbsp;&nbsp;');
    renderLink(currentPageNum + 1, 'Next Page &raquo;');
  }

  div.innerHTML = html.join('');
  // pagination debugging
  //div.innerHTML += "<br/>totalNum="+totalNum
  //div.innerHTML += "<br/>currentPageNum="+currentPageNum;
  //div.innerHTML += "<br/>numPages="+numPages;
  //div.innerHTML += "<br/>forceShowNextLink="+forceShowNextLink;
  
}

/** Loads the Maps API asynchronously and notifies the asynchronous load
 * manager on completion.
 */
initMap = function() {
  var initialized = false;
  return function() {
    if (!initialized) {
      google.load('maps', '2',
          { 'callback' : function() {
              // Maps API is now loaded.  First initialize
              // the map object, then execute any
              // map-dependent functions that are queued up.
              map = new SimpleMap(el('map'));
              asyncLoadManager.doneLoading('map');
           }});
      initialized = true;
    }
  };
}(); // executed inline to close over the 'initialized' variable.

/** A single search result.
 * @constructor
 * @param {string} url a url.
 * @param (string) url_sig the signature of the url.
 * @param {string} title a title.
 * @param {string} location a location.
 * @param {string} snippet a snippet.
 * @param {Date} startdate a start date.
 * @param {Date} enddate an end date.
 * @param {string} itemId the item id.
 * @param {string} baseUrl the base url.
 * @param {boolean} liked flag if liked.
 * @param {number} totalInterestCount total users who flagged interest.
 * @param {string} hostWebsite the website hosting the event (volunteermatch.org etc).
 */
function SearchResult(url, url_sig, title, location, snippet, startdate, enddate,
                      itemId, baseUrl, liked, totalInterestCount, hostWebsite) {
  this.url = url;
  this.url_sig = url_sig;
  this.title = title;
  this.location = location;
  this.snippet = snippet;
  this.startdate = startdate;
  this.enddate = enddate;
  this.itemId = itemId;
  this.baseUrl = baseUrl;
  this.liked = liked;
  this.totalInterestCount = totalInterestCount;
  this.hostWebsite = hostWebsite;
}

var lastSearchQuery = new Query('', '', 0, {}, 1);
var whenFilterWidget;

asyncLoadManager.addCallback('bodyload', onLoadSearch);
