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
      var category = $("#category_input");
      if (category.val()) {
    	  vol_loc += "&category=" + category.val();
      }      
      var source = $("#provider_input");
      if (source.val()) {
    	  vol_loc += "&source=" + source.val();
      }
	  var sort = getInputFieldValue(el('sort'));
	  vol_loc += "&sort=" + (sort || 'score');
      window.location = '/search#q=' +
          escape(getInputFieldValue(el('keywords'))) +
          vol_loc;
    }
  }
}

function setCategory(category) {
	var category_input = $("#category_input");
	if (category_input) {
		category_input.val(category);
		submitForm('category');
	}	
}

function sortResults(value) {
  setInputFieldValue(el('sort'), value);
  submitForm('sort', value);
}

function createExampleSearchText() {
  // Put categories to receive the "New!" superscript in here
  var new_popular = [] // ["September 11"]
  var html = 'Categories: ';
  var links = [];
  for (var i = 0; i < popularSearches.length; i++) {
    var pop_str = popularSearches[i][0] + '</a>'
    links.push('<a onclick="setCategory(\'' + 
                popularSearches[i][1] + '\');return false;"' +
        'href="javascript:void(0);">' + pop_str);
  }
  el('example_searches').innerHTML = html + links.join(', ');
}
