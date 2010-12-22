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

function submitCategory(category) {
    window.location = '/search#category=' + category;
}

function createExampleSearchText() {
  var new_popular = []
  var html = 'Categories: ';
  var links = [];
  for (var i = 0; i < popularSearches.length; i++) {
    var pop_str = popularSearches[i][0] + '</a>'
    links.push('<a onclick="submitCategory(\'' + 
                popularSearches[i][1] + '\');return false;"' +
        'href="javascript:void(0);">' + pop_str);
  }
  el('example_searches').innerHTML = html + links.join(', ');
}
