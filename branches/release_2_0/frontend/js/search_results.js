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
var filters = [];

$(document).ready(function() {    
	var index = getSelectedTab();
	$("#tabs").tabs({			
		select: function(event, ui) {			
			submitForm('oppType', ui.index);								 
		},
		selected: index,
		collapsible: true
	});
	$("#startdate").datepicker({
		minDate: new Date(),
		onSelect: function(dateText, inst) {
			$("#enddate").datepicker("option", "minDate", dateText);
		}
	});
	$("#enddate").datepicker({
		minDate: new Date()        		
	});
	$("#location_slider").slider({
			value:getHashParam('distance', '') || 25,
			min: 5,
			max: 100,
			step: 5,
			slide: function(event, ui) {
				$("#location_distance").html(ui.value);
			},
			stop: function(event, ui) {
				submitForm("all");
			}
	});	
	$("#location_distance").html($("#location_slider").slider("value"));	
	$("#facet_submit").click(function() {
		submitForm("all");
		return false;
	});
	$("#location").keypress(function(e) {
		code = (e.keyCode ? e.keyCode : e.which);
		if (code == 13) {
			submitForm("all");
			return false;
		}		
	});
	var start = getHashParam('timeperiodstart', '');
	var end = getHashParam('timeperiodend', '');	
	if (start != "everything") {
		getInputFieldValue(el('startdate')).value = start;
	}
	if (end != "everything") {
		getInputFieldValue(el('enddate')).value = end;
	}
  });
  
  function getSelectedTab() {
  	var type = getHashParam('type', '');
	var index = 0;		
	if (type == "virtual")
		index = 1;
	else if (type == "self_directed")
		index = 2;
	else if (type == "micro")
		index = 3;
	else
		index = 0;
	return index;
  }
  
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
function Query(keywords, location, distance, type, pageNum, sort, useCache, get_facet_counts, opt_timePeriodStart, opt_timePeriodEnd, opt_filters) {
  var me = this;
  me.keywords_ = keywords;
  me.location_ = location;
  //me.category_ = category || 'all';
  me.distance_ = distance || '25';
  me.type_ = type || 'all';
  //me.source_ = source || 'all';
  me.pageNum_ = pageNum;
  me.sort_ = sort;
  me.use_cache_ = useCache;
  me.get_facet_counts_ = get_facet_counts || true;
  me.timePeriodStart_ = opt_timePeriodStart || 'everything';
  me.timePeriodEnd_ = opt_timePeriodEnd || 'everything';
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

Query.prototype.getFacetCounts = function() {
  return this.get_facet_counts_;
}

Query.prototype.setKeywords = function(keywords) {
  this.keywords_ = keywords;
};

Query.prototype.getLocation = function() {
  return this.location_;
};

Query.prototype.setLocation = function(location) {
  this.location_ = location;
};

Query.prototype.setCategory = function(category) {
  this.category_ = category;
};

Query.prototype.getCategory = function() {
  return this.category_;
};

Query.prototype.setDistance = function(distance) {
  this.distance_ = distance;
};

Query.prototype.getDistance = function() {
  return this.distance_;
};

Query.prototype.setType = function(type) {
  if (type == "1")
  	this.type_ = "virtual";
  else if (type == "2")
  	this.type_ = "self_directed";
  else if (type == "3")
    this.type_ = "micro";
  else
    this.type_ = "all";	
};

Query.prototype.getType = function() {
  return this.type_;
};

Query.prototype.setSource = function(source) {
  this.source_ = source;
};

Query.prototype.getSource = function() {
  return this.source_;
};

Query.prototype.setSort = function(sort) {
  this.sort_ = sort;
};

Query.prototype.getSort = function() {
  return this.sort_;
};

Query.prototype.getTimePeriodStart = function() {
  return this.timePeriodStart_;
};

Query.prototype.setTimePeriodStart = function(period) {
  this.timePeriodStart_ = period;
};

Query.prototype.getTimePeriodEnd = function() {
  return this.timePeriodEnd_;
};

Query.prototype.setTimePeriodEnd = function(period) {
  this.timePeriodEnd_ = period;
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
  var facet_fields_added = 0;
  var facet_queries_added = 0;
  function addQueryParam(name, value) {
    if (urlQuery.length > 0) {
      urlQuery += '&';
    }
    urlQuery += name + '=' + escape(value);
  }
  function addFacetField(value) {
    addQueryParam('facet.field' + facet_fields_added++, value);
  }
  function addFacetQuery(value) {
	addQueryParam('facet.query' + facet_queries_added++, value);
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
  
  // Distance
  var distance = me.getDistance();
  if (distance && distance.length > 0) {
    addQueryParam('distance', distance);
  }
  
   // Type
  var type = me.getType();
  if (type && type.length > 0) {
    addQueryParam('type', type);
  }
  
  // Sort
  var sort = me.getSort();
  if (sort && sort.length > 0) {
    addQueryParam('sort', sort);
  }

  // Time period
  var periodStart = me.getTimePeriodStart();
  if (periodStart) {
    addQueryParam('timeperiodstart', periodStart)
  }
  var periodEnd = me.getTimePeriodEnd();
  if (periodEnd) {
    addQueryParam('timeperiodend', periodEnd)
  }

  // Add additional filters to query URL.
  for (var name in me.filters_) {
    var value = me.getFilter(name);
    if (value) {
      addQueryParam(name, value);
    }
  }
  if (me.getFacetCounts())
  {
    var facetFieldCount = 0;
    //addQueryParam('facet', 'true');
    //addQueryParam('facet.limit', '-1');
	//addQueryParam('facet.mincount', '1');
    //addFacetField('feed_providername');
	//addFacetField('categories');
	//addFacetField('virtual');
	//addFacetField('self_directed');
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
  var location = getHashParam('vol_loc', getDefaultLocation().displayLong);
  var category = getHashParam('category', '');
  var distance = getHashParam('distance', '');
  var type = getHashParam('type', '');
  var source = getHashParam('source', '');
  var sort = getHashParam('sort', '');
  var start = Number(getHashParam('start', '1'));  
  var timePeriodStart = getHashParam('timeperiodstart');
  var timePeriodEnd = getHashParam('timeperiodend');
  var use_cache = Number(getHashParam('cache', '1'));
  var get_facet_counts = getHashParam('facet', 'true');
  start = Math.max(start, 1);
  var numPerPage = Number(getHashParam('num', NUM_PER_PAGE));
  numPerPage = Math.max(numPerPage, 1);
  var pageNum = (start - 1) / numPerPage;
  var filters = {};

  // Read in the other filters from the URL, and place them in
  // 'filters' object.
  function getNamedFilterFromUrl(name) {
    filters[name] = getHashParam(name, '');
  }
  
  getNamedFilterFromUrl('bf');
  getNamedFilterFromUrl('bft');
  getNamedFilterFromUrl('vol_dist');
  getNamedFilterFromUrl('vol_startdate');
  getNamedFilterFromUrl('vol_enddate'); 
  getNamedFilterFromUrl('key');

  return new Query(keywords, location, distance, type, pageNum, sort, use_cache, get_facet_counts, timePeriodStart, timePeriodEnd, filters);
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
  filters.push(me);
  me.render();
}

FilterWidget.prototype.render = function(oldValue) {
  var me = this;
  oldValue = typeof oldValue == undefined ? '' : oldValue;
  var titleDiv = document.createElement('div');
  var catLink = document.createElement('a');
  titleDiv.className = 'filterwidget_title';
  catLink.innerHTML = me.title_;
  catLink.href = 'javascript:void(0)';
  //catLink.onclick = expandFilterWidget(me);
  titleDiv.appendChild(catLink);
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
	
	var display = me.entries_[i][0];
	if (me.entries_[i].length >= 3 && me.entries_[i][1] != oldValue)
	{
		display += ' (' + me.entries_[i][2] + ')';
	}

    if (me.entries_[i][1] == me.value_) {
      entryDiv.innerHTML = '<b>' + me.entries_[i][0] + '</b>';
    } else {
      var link = document.createElement('a');
      link.innerHTML = display;
      link.href = 'javascript:void(0)';
      link.onclick = clickCallback(i);
      entryDiv.appendChild(link);
    }
  }
};

FilterWidget.prototype.isDefault = function() { 
	return (this.value_ == this.entries_[0][1]);
};

FilterWidget.prototype.getValue = function() {
  return this.value_;
};

FilterWidget.prototype.setValue = function(newValue) {
  var me = this;
  var oldValue = me.value_;
  me.value_ = newValue;
  me.render(oldValue);
};

FilterWidget.prototype.getName = function() {
  var me = this;
  for (var i = 0; i < me.entries_.length; i++)
  {
    if (me.entries_[i][1] == me.value_)
	  return me.entries_[i][0];
  }
}

/** Perform a search using the current URL parameters and IP geolocation.
 */
function onLoadSearch() {
  if (el('location')) {
    setInputFieldValue(el('location'), getHashParam('vol_loc', '') || getDefaultLocation().displayLong);
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

function populateSearchHistory()
{
	if (el('filter_results'))
	{
		var me = el('filter_results');
		var titleDiv = document.createElement('div');
		var catLink = document.createElement('a');
		titleDiv.className = 'filterwidget_title';
		catLink.innerHTML = 'Search History';
		catLink.href = 'javascript:void(0)';
		titleDiv.appendChild(catLink);
		me.innerHTML = '';
		me.appendChild(titleDiv);
		for (var i = 0; i < filters.length; i++)
		{
			var filt = filters[i];
			if (!filt.isDefault())
			{
				var entryDiv = document.createElement('div');
				entryDiv.className = 'filterwidget_entry';
				me.appendChild(entryDiv);
				var change = document.createElement('b');
				change.innerHTML = filt.getName() + "&nbsp;&nbsp;&nbsp;";
				entryDiv.appendChild(change);
				var link = document.createElement('a');
				link.innerHTML = '(undo)';
				link.href = 'javascript:void(0)';
				link.onclick = filt.setValue(0);
				entryDiv.appendChild(link);
			}
		}
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
	  //populateSearchHistory();
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
	jQuery(this).ajaxStop(function() { scroll(0,0); });
  };
}(); // executed inline to close over the 'currentXhr' variable.

function getStartDate()
{
  var start = getInputFieldValue(el('startdate')).toString();
  if (!start || start == "Start Date") {
	start = "";
  }  
  return start;
}
function getEndDate()
{
  var end = getInputFieldValue(el('enddate')).toString();
  if (!end || end == "End Date") {
  	end = "";
  }  
  return end;
}

function getDistance() {
	return $("#location_slider").slider("value").toString();
}

/** Called from the "Refine" button's onclick, the main form onsubmit,
 * and the time period filter.
 * @param {string} invoker Who invoked this submission?  One of
 *                         ['keywords', 'when_widget', 'map'].
 */
function submitForm(invoker, value) {  
  var keywords = getInputFieldValue(el('keywords'));

  // If the keywords search form is invoked from non-search page,
  // redirect to search page.
  if (invoker == 'category' && currentPageName != 'SEARCH') {
    // TODO: Incorporate current 'when' filter?
    window.location = '/search#category=' + value;
    return;
  }
  
  if (invoker == 'sort' && currentPageName != 'SEARCH') {
  	window.location = '/search#sort=' + value;
    return;
  }

  var location = getInputFieldValue(el('location'));	
  if (invoker == 'map') {
    setSessionCookie('user_vol_loc', location);
  } 

  var timePeriodStart = getStartDate();
  var timePeriodEnd = getEndDate();
  var distance = getDistance();
  var sort = getInputFieldValue(el('sort'));
  if (location == '') {
    location = getDefaultLocation().displayLong;
  }  
  
  var query = lastSearchQuery.clone();
  query.setKeywords(keywords);
  query.setLocation(location);
  query.setDistance(distance);  
  if (invoker == "oppType") {
  	query.setType(value);
	var type = query.getType();
	$(".facets").css("visibility", "visible");
	$(".top_search").css("visibility", "visible");
	if (type == "all") {		
		$("#location_box").show();
        $("#map").css("visibility", "visible");
    }
    else {        
		$("#location_box").hide();
        $("#map").css("visibility", "hidden");		
		if (type == "self_directed") {			
			$(".top_search").css("visibility", "hidden");
			$(".facets").css("visibility", "hidden");
		}
    }
  }
  query.setPageNum(0);
  query.setSort(sort);
  query.setTimePeriodStart(timePeriodStart);
  query.setTimePeriodEnd(timePeriodEnd);
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

(function($){
	$.fn.expand = function(options) {	   
		var defaults = {
			length: 285,
			minTrail: 20,
			moreText: "[more]",
			lessText: "[less]",
			ellipsisText: "... ",
			moreAni: "",
			lessAni: ""
		};		
		var options = $.extend(defaults, options);	   
		return this.each(function() {
			obj = $(this);
			var body = obj.html();			
			if (body.length > options.length + options.minTrail) {
				var splitLocation = body.indexOf(' ', options.length);
				if (splitLocation != -1) {
					// truncate tip
					var splitLocation = body.indexOf(' ', options.length);
					var str1 = body.substring(0, splitLocation);
					var str2 = body.substring(splitLocation, body.length - 1);
					obj.html(str1 + '<span class="truncate_ellipsis">' + options.ellipsisText + 
						'</span>' + '<span class="truncate_more">' + str2 + '</span>');
					obj.find('.truncate_more').css("display", "none");
					
					// insert more link
					obj.append(
						'<span class="clearboth">' +
							'<a href="#" class="truncate_more_link">' + options.moreText + '</a>' +
						'</span>'
					);

					// set onclick event for more/less link
					var moreLink = $('.truncate_more_link', obj);
					var moreContent = $('.truncate_more', obj);
					var ellipsis = $('.truncate_ellipsis', obj);
					moreLink.click(function() {
						if (moreLink.text() == options.moreText) {
							moreContent.show(options.moreAni);
							moreLink.text(options.lessText);
							ellipsis.css("display", "none");
						} else {
							moreContent.hide(options.lessAni);
							moreLink.text(options.moreText);
							ellipsis.css("display", "inline");
						}
						return false;
				  	});
				}
			} // end if
			
		});
	};
})(jQuery);

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
  if (numPages == 1) {
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

  if (currentPageNum != numPages - 1) {
    html.push('&nbsp;&nbsp;&nbsp;');
    renderLink(currentPageNum + 1, 'Next Page &raquo;');
  }

  div.innerHTML = html.join('');
  // pagination debugging
  //div.innerHTML += "<br/>totalNum="+totalNum
  //div.innerHTML += "<br/>currentPageNum="+currentPageNum;
  //div.innerHTML += "<br/>numPages="+numPages;  
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

var lastSearchQuery = new Query('', '','', 0, true, {}, 1);
var whenFilterWidget;
var typeFilterWidget;
var sourceFilterWidget;
var distanceFilterWidget;
var categoryFilterWidget;

asyncLoadManager.addCallback('bodyload', onLoadSearch);
