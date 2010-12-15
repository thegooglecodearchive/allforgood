/* functions for search UI */

/* Handle searches on static content pages. */
function ensureSubmitForm() {
  if (!('submitForm' in window)) {
    window.submitForm = function(fromWhere) {
      var vol_loc = '';
      if (el('location')) {
        var location = getInputFieldValue(el('location'));
        vol_loc = '&vol_loc=' + escape(location);
        setSessionCookie('user_vol_loc', location);
      }
      if (fromWhere == 'virtual_location') {
        vol_loc += '&virtual=1'
      }
      window.location = '/search#q=' +
          escape(getInputFieldValue(el('keywords'))) +
          vol_loc;
    }
  }
}

function setKeywordAndExecute(keywords) {
  if (keywords == 'OilSpill') {
    keywords = '"Oil Spill"';
  }
  else if (keywords == 'Veterans Day') {
    keywords = 'veterans';
  }
  setInputFieldValue(el('keywords'), keywords);
  submitForm('keywords');
}

function createExampleSearchText() {
  // Put categories to receive the "New!" superscript in here
  var new_popular = [] // ["September 11"]
  var html = 'Categories: ';
  var links = [];
  for (var i = 0; i < popularSearches.length; i++) {
    var pop_str = popularSearches[i] + '</a>'
    /*
    if (new_popular.indexOf(popularSearches[i]) != -1){
      var pop_str = popularSearches[i] + "</a><span class='new_pop'>New!</span>"
    } else {
      var pop_str = popularSearches[i] + '</a>'
    }
    */
    if (popularSearches[i] && popularSearches[i].indexOf('OilSpill') >= 0) {
      links.push('<a onclick="setKeywordAndExecute(\'OilSpill\');return false;"' +
        'href="javascript:void(0);">' + pop_str);
    } else if (popularSearches[i] && popularSearches[i].indexOf('EarthDay') >= 0) {
      links.push('<a onclick="setKeywordAndExecute(\'Nature\');return false;"' +
        'href="javascript:void(0);">' + pop_str);
    } else if (popularSearches[i] && popularSearches[i].indexOf('Chile') >= 0) {
      links.push('<a onclick="setKeywordAndExecute(\'Chile\');return false;"' +
        'href="javascript:void(0);">' + pop_str);
    } else if (popularSearches[i] && popularSearches[i].indexOf('Haiti') >= 0) {
      links.push('<a onclick="setKeywordAndExecute(\'Haiti\');return false;"' +
        'href="javascript:void(0);">' + pop_str);
    } else {
      links.push('<a onclick="setKeywordAndExecute(\'category:' + 
                popularSearches[i].replace(" ", "") + '\');return false;"' +
        'href="javascript:void(0);">' + pop_str);
    }
  }
  el('example_searches').innerHTML = html + links.join(', ');
}
