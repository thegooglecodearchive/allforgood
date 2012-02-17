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

function el(id) {
  return document.getElementById(id);
}

function setTextContent(el, text) {
  el.innerHTML = '';
  el.appendChild(document.createTextNode(text));
}

function popupModalElement(node) {
  var hider = document.createElement('div');
  var style = hider.style;
  style.position = 'absolute';
  style.zIndex = '5';
  style.left = '0px';
  style.top = '0px';
  style.height = '100%';
  style.width = '100%';
  document.body.appendChild(hider);

  var hide = function() {
    node.style.visibility = 'hidden';
    document.body.removeChild(hider);
  }

  if (typeof node == 'string') {
    node = el(node);
  }
  node.style.visibility = 'visible';

  var clickCallback;
  clickCallback = function(event) {
    hide();
    setTimeout(function(){
          removeListener(document.body, 'click', clickCallback);
        }, 10);
    return true;
  };
  setTimeout(function() {
        addListener(document.body, 'click', clickCallback);
      }, 10);

  addListener(node, 'move', function(event) {
    if (window.event) {
      event = window.event;
    }
    if (event.target == node) {
      if ('cancelBubble' in event) {
        event.cancelBubble = true;
      } else if ('stopPropagation' in event) {
        event.stopPropagation();
      }
    }

    hide();
  });
}

function hideEl(divOrDivName) {
  if (typeof divOrDivName == 'string')
    divOrDivName = el(divOrDivName);
  divOrDivName.style.display = 'none';
}

function explode(obj) {
  var s = '';
  for (i in obj) {
    s += i + ':' + obj[i] + ' . . . ';
  }
}

function forEach(array, fn) {
  var l = array.length;
  for (var i = 0; i < l; i++) {
    fn(array[i], i);
  }
}

function forEachElementOfClass(classname, fn, opt_element) {
  var root = opt_element || document;
  var elements;
  if (root.getElementsByClassName) {
    elements = root.getElementsByClassName(classname);
  } else {
    // Dustin Diaz's implementation.
    // http://ejohn.org/blog/getelementsbyclassname-speed-comparison
    var elements = new Array();
    var tag = '*';
    var els = root.getElementsByTagName(tag);
    var elsLen = els.length;
    var pattern = new RegExp("(^|\\s)" + classname + "(\\s|$)");
    for (i = 0; i < elsLen; i++) {
      if (pattern.test(els[i].className)) {
        elements.push(els[i]);
      }
    }
  }
  forEach(elements, fn);
}

function addListener(element, type, callback) {
  if (element.addEventListener) {
    element.addEventListener(type, callback, false);
  } else if (element.attachEvent) {
    element.attachEvent('on' + type, function() {
        callback(window.event);
    });
  } else {
    element['on' + type] = callback;
  }
}

function removeListener(element, type, callback) {
  if (element.removeEventListener) {
    element.removeEventListener(type, callback, false);
  } else if (element.detachEvent) {
    element.detachEvent('on' + type, callback);
  } else {
    element['on' + type] = callback;
  }
}

/**
 * Gets a map of params from the given URL.
 * @param {string} paramString The URL params to process.
 * @return {Object} The map of key/values.
 */
function getUrlParams(paramString) {
  // Decode URL hash params.
  var params = {};
  var pairs = paramString.split('&');
  for (var i = 0; i < pairs.length; i++) {
    var p = pairs[i].split('=');
    var paramval = undefined;
    var decodedName = decodeURIComponent(p[0]);
    if (decodedName.length > 0) {
      if (p.length > 1) {
        paramval = decodeURIComponent(p[1]);
      }
      params[decodedName] = paramval;
    }
  }
  return params;
}

var cachedParams_ = {};

/**
 * Retrieves a parameter from the browser URL, as managed by RSH. If RSH doesn't
 * have a valid value then fall back to the direct hashstring.
 * Note: this function caches the processed parameters, keyed to the URL's.
 *
 * @param {string} paramName Parameter name
 * @param {string} opt_defaultValue Default value returned by this function if
 *     the parameter does not exist. If left unspecified, the function returns
 *     {@code null}.
 */
function getHashParam(paramName, opt_defaultValue) {
  var location = window.location.hash.substring(1); // Removes '#'.
  var params = cachedParams_[location];
  if (!params) {
    params = getUrlParams(location);
    cachedParams_[location] = params;
  }
  val = params[paramName];
  if (val === '') {
    return val;
  }

  return val || opt_defaultValue || null;
}


/** Count number of elements inside a JS object */
function getObjectLength(object) {
  var count = 0;
  for (i in object) {
    count++;
  }
  return count;
}

/* Queues up a series of JS callbacks, which are executed when execute()
  is called. */
function WorkQueue() {
  this.queue_ = [];
}

WorkQueue.prototype.execute = function() {
  for (var i = 0; i < this.queue_.length; i++) {
    this.queue_[i]();
  }
  // Clear the queue.
  this.queue_ = [];
}

WorkQueue.prototype.addCallback = function(callback) {
  this.queue_.push(callback);
}

/**
 * Class to manage the asynchronous loading of components at runtime.
 * When this class is created, give it an array of strings, where
 * each string corresponds to a load eventname.  Register functions for
 * each eventname.  Later, when appropriate, call the function
 * doneLoading(eventName) to trigger each registered function for that
 * eventname.  Now, this is almost exactly like a regular event registration
 * system, except: (1) if a particular load type already occurred
 * BEFORE a function callback is registered, that callback will be
 * triggered immediately; and (2) each load-event is only ever triggered once.
 * The first point above is a reason to use AsyncLoadManager instead of
 * body.onload or the equivalent events in jQuery or other toolkits:
 * this class guarantees that the callback dispatches even if it is
 * registered after the event fires.
 *
 * @param {Array} eventNamesArray Array of strings, the load eventnames.
 **/
function AsyncLoadManager(eventNamesArray) {
  this.callbacks_ = {};
  this.loadStatus_ = {};

  for (var i = 0; i < eventNamesArray.length; i++) {
    var eventName = eventNamesArray[i]
    this.loadStatus_[eventName] = false;
    this.callbacks_[eventName] = new WorkQueue();
  }
}

/** Register a callback for a given load type (eventName).
 * The eventName must have been part of eventNamesArray in the class ctor.
 */
AsyncLoadManager.prototype.addCallback = function(eventName, callback) {
  if ((eventName in this.loadStatus_) && (eventName in this.callbacks_)) {
    if (this.loadStatus_[eventName] == true) {
      // This load event already completed.  Execute the callback immediately.
      callback();
    } else {
      // Load event hasn't yet completed.  Queue it up.
      this.callbacks_[eventName].addCallback(callback);
    }
  }
}

/** Mark a load event as having completed.  This executes all pending
 * callbacks for that event.
 */
AsyncLoadManager.prototype.doneLoading = function(eventName) {
  if ((eventName in this.loadStatus_) && (eventName in this.callbacks_)) {
    if (this.loadStatus_[eventName] == false) {
      this.loadStatus_[eventName] = true;
      this.callbacks_[eventName].execute();
    }
  }
}

AsyncLoadManager.prototype.isLoaded = function(eventName) {
  return (eventName in this.loadStatus_  &&
          this.loadStatus_[eventName] == true);
}

/** Get the IP geolocation given by the Common Ajax Loader.
 * Note: this function caches its own result.
 * @return {string} the current geolocation of the client, if it is known,
 *     otherwise an empty string.
 */
getDefaultLocation = function() {
  var clientLocation;
  return function() {
    if (clientLocation === undefined) {
      try {
        var loc = google.loader.ClientLocation;
        var clientLocationString = loc.latitude + "," + loc.longitude;

        clientLocation = { 'coords': clientLocationString,
                           'displayShort': '',
                           'displayLong': '' };

        if (loc.address.city) {
          clientLocation.displayLong = loc.address.city;
          clientLocation.displayShort = loc.address.city;
          if (loc.address.region) {
            clientLocation.displayLong += ', ' + loc.address.region;
          }
        }
      } catch (err) {
        clientLocation = { 'coords': '',
                           'displayShort': '',
                           'displayLong': '' };
      }
    }
    var userVolLocCookie = getSessionCookie('user_vol_loc');
    if (userVolLocCookie) {
      return { 'coords': userVolLocCookie,
               'displayShort': userVolLocCookie,
               'displayLong': userVolLocCookie };
    } else {
      return clientLocation;
    }
  };
}();  // executed inline to close over the 'clientLocationString' variable.

function trimString(string) {
	return string.replace(/^\s+|\s+$/g, '');
}

/**
 * Populate a text input field with a value, and revert to input.defaultValue
 * when value is ''.
 * @param {HTMLInputerElement} input Input element.
 * @param {string} value Value to set Input field to.
 */
function setInputFieldValue(input, value) {
  if (!input) {
    return;
  }

  function set(valueToSet) {
    valueToSet = trimString(valueToSet || '');

    if (valueToSet == '') {
      input.style.color = '#666';
      input.value = input.name || '';

      input.onfocus = function() {
        if (input.value && input.name && input.value == input.name) {
          input.value = '';
        }

        input.style.color = 'black';
        input.onfocus = null;
      }
    } else {
      input.style.color = 'black';
      //input.value = encodeURIComponent(valueToSet).replace(/%20/g, ' ').replace(/%3A/gi, ':').replace(/%2C/gi, ',').replace(/%22/g, '"');
      input.value = valueToSet;
    }
  }

  input.onblur = function() {
    set(input.value);
  }

  set(value);
}

/**
 * Retrieves the value of an inputfield, but returns '' if value==defaultValue
 * @param {HTMLInputElement} input Input element.
 */
function getInputFieldValue(input) {
  if (!input || !input.value || input.value == input.name) {
    return '';
  } else {
    return input.value;
  }
}

var SESSION_COOKIE_PREFIX = 'allforgood_';
function setSessionCookie(name, value) {
  value = trimString(value || '');  // Force string so we don't write
                                    // 'undefined' or 'null'
  document.cookie = SESSION_COOKIE_PREFIX +
    escape(name) + '=' + escape(value);
}

function getSessionCookie(name) {
  var prefixedName = SESSION_COOKIE_PREFIX + escape(name);
  var cookies = document.cookie.split(';');
  for (var i = 0; i < cookies.length; i++) {
    var pair = cookies[i].split('=');
    var cookieName = pair[0];
    var cookieValue = pair[1];
    while (cookieName.charAt(0) == ' ') {
      cookieName = cookieName.substring(1, cookieName.length);
    }
    if (cookieName == prefixedName) {
      if (pair[1]) {
        return unescape(pair[1]);
      } else {
        return '';
      }
    }
  }
  return undefined;
}

function clearExternalCookies() {
  var cookiesToClear = [];
  var cookies = document.cookie.split(';');
  for (var i = 0; i < cookies.length; i++) {
    var pair = cookies[i].split('=');
    var cookieName = pair[0];
    var cookieValue = pair[1];
    if (cookieName.indexOf(SESSION_COOKIE_PREFIX) == -1) {
      cookiesToClear.push(cookieName);
    }
  }

  for (var i = 0; i < cookiesToClear.length; i++) {
    var cookieName = cookiesToClear[i];
    document.cookie = cookieName + '=;path=/;';
  }
}

// Define console.log in case it's not already.
try {
  if (!('console' in window)) {
    var console = {};
    console.text_ = '';
    console.visible_ = false;
    console.div_ = null;
    console.log = function(text) {
      if (getHashOrQueryParam('debugjs') != null) {
        if (!console.visible_) {
          console.visible_ = true;
          console.div_ = document.createElement('div');
          console.div_.style.border = '1px solid silver';
          console.div_.style.padding = '4px';
          document.body.appendChild(console.div_);
        }
        console.text_ += text + '<br>';
        console.div_.innerHTML = console.text_;
      }
    }
  }
} catch(err) {}

/*
 * Date Format 1.2.3
 * (c) 2007-2009 Steven Levithan <stevenlevithan.com>
 * MIT license
 *
 * Includes enhancements by Scott Trenda <scott.trenda.net>
 * and Kris Kowal <cixar.com/~kris.kowal/>
 *
 * Accepts a date, a mask, or a date and a mask.
 * Returns a formatted version of the given date.
 * The date defaults to the current date/time.
 * The mask defaults to dateFormat.masks.default.
 */

var dateFormat = function () {
	var	token = /d{1,4}|m{1,4}|yy(?:yy)?|([HhMsTt])\1?|[LloSZ]|"[^"]*"|'[^']*'/g,
		timezone = /\b(?:[PMCEA][SDP]T|(?:Pacific|Mountain|Central|Eastern|Atlantic) (?:Standard|Daylight|Prevailing) Time|(?:GMT|UTC)(?:[-+]\d{4})?)\b/g,
		timezoneClip = /[^-+\dA-Z]/g,
		pad = function (val, len) {
			val = String(val);
			len = len || 2;
			while (val.length < len) val = "0" + val;
			return val;
		};

	// Regexes and supporting functions are cached through closure
	return function (date, mask, utc) {
		var dF = dateFormat;

		// You can't provide utc if you skip other args (use the "UTC:" mask prefix)
		if (arguments.length == 1 && Object.prototype.toString.call(date) == "[object String]" && !/\d/.test(date)) {
			mask = date;
			date = undefined;
		}

		// Passing date through Date applies Date.parse, if necessary
		date = date ? new Date(date) : new Date;
		if (isNaN(date)) throw SyntaxError("invalid date");

		mask = String(dF.masks[mask] || mask || dF.masks["default"]);

		// Allow setting the utc argument via the mask
		if (mask.slice(0, 4) == "UTC:") {
			mask = mask.slice(4);
			utc = true;
		}

		var	_ = utc ? "getUTC" : "get",
			d = date[_ + "Date"](),
			D = date[_ + "Day"](),
			m = date[_ + "Month"](),
			y = date[_ + "FullYear"](),
			H = date[_ + "Hours"](),
			M = date[_ + "Minutes"](),
			s = date[_ + "Seconds"](),
			L = date[_ + "Milliseconds"](),
			o = utc ? 0 : date.getTimezoneOffset(),
			flags = {
				d:    d,
				dd:   pad(d),
				ddd:  dF.i18n.dayNames[D],
				dddd: dF.i18n.dayNames[D + 7],
				m:    m + 1,
				mm:   pad(m + 1),
				mmm:  dF.i18n.monthNames[m],
				mmmm: dF.i18n.monthNames[m + 12],
				yy:   String(y).slice(2),
				yyyy: y,
				h:    H % 12 || 12,
				hh:   pad(H % 12 || 12),
				H:    H,
				HH:   pad(H),
				M:    M,
				MM:   pad(M),
				s:    s,
				ss:   pad(s),
				l:    pad(L, 3),
				L:    pad(L > 99 ? Math.round(L / 10) : L),
				t:    H < 12 ? "a"  : "p",
				tt:   H < 12 ? "am" : "pm",
				T:    H < 12 ? "A"  : "P",
				TT:   H < 12 ? "AM" : "PM",
				Z:    utc ? "UTC" : (String(date).match(timezone) || [""]).pop().replace(timezoneClip, ""),
				o:    (o > 0 ? "-" : "+") + pad(Math.floor(Math.abs(o) / 60) * 100 + Math.abs(o) % 60, 4),
				S:    ["th", "st", "nd", "rd"][d % 10 > 3 ? 0 : (d % 100 - d % 10 != 10) * d % 10]
			};

		return mask.replace(token, function ($0) {
			return $0 in flags ? flags[$0] : $0.slice(1, $0.length - 1);
		});
	};
}();

// Some common format strings
dateFormat.masks = {
	"default":      "ddd mmm dd yyyy HH:MM:ss",
	shortDate:      "m/d/yy",
	mediumDate:     "mmm d, yyyy",
	longDate:       "mmmm d, yyyy",
	fullDate:       "dddd, mmmm d, yyyy",
	shortTime:      "h:MM TT",
	mediumTime:     "h:MM:ss TT",
	longTime:       "h:MM:ss TT Z",
	isoDate:        "yyyy-mm-dd",
	isoTime:        "HH:MM:ss",
	isoDateTime:    "yyyy-mm-dd'T'HH:MM:ss",
	isoUtcDateTime: "UTC:yyyy-mm-dd'T'HH:MM:ss'Z'"
};

// Internationalization strings
dateFormat.i18n = {
	dayNames: [
		"Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat",
		"Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"
	],
	monthNames: [
		"Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
		"January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"
	]
};

// For convenience...
Date.prototype.format = function (mask, utc) {
	return dateFormat(this, mask, utc);
};
