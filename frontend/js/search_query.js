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
      window.location = '/search#q=' +
          escape(getInputFieldValue(el('keywords'))) +
          vol_loc;
    }
  }
}

function setKeywordAndExecute(keywords) {
  setInputFieldValue(el('keywords'), keywords);
  submitForm('keywords');
}

function createExampleSearchText() {
  var html = 'Categories: ';
  var links = [];
  for (var i = 0; i < popularSearches.length; i++) {
    links.push('<a onclick="setKeywordAndExecute(\'category:' + popularSearches[i] +
        '\');return false;"' +
        'href="javascript:void(0);">' + popularSearches[i] + '</' + 'a>');
  }
  el('example_searches').innerHTML = html + links.join(', ');
}
