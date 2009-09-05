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

function goPopular(index) {
  setInputFieldValue(el('keywords'), 'category:'.popularSearches[index]);
  submitForm('');
}

/* requires that google /jsapi has been loaded... */
var defaultLocation = getDefaultLocation().displayLong || '';
function runSnippetsQuery() {
  var vol_loc_term;
  if (defaultLocation != '') {
    vol_loc_term = '&vol_loc=' + defaultLocation;
  } else {
    /* TODO: Move defaults to search.py/base_search.py, then
       test that "No Results" message doesn't show "USA". */
    vol_loc_term = '&vol_loc=USA&vol_dist=1500';
  }
  var url = '/ui_snippets?start=0&num=15&minimal_snippets_list=1' + vol_loc_term;
  jQuery.ajax({
        url: url,
        async: true,
        dataType: 'html',
        error: function(){},
        success: function(data){
          if (data.length > 10) {  // Check if data is near-empty.
            el('snippets').innerHTML = data;
            el('more').style.display = '';
          }
          // Load analytics, done here to ensure search is finished first
          // Only loading for homepage here - loaded in search_resuls.js
          // for search pages and base.html for static pages
          loadGA();
        }
      });
}

function renderHomepage() {
  // render homepage elements
  setInputFieldValue(el('location'), defaultLocation);
  if (defaultLocation != '') {
    el('mini_with_location').style.display = '';
  } else {
    el('mini_without_location').style.display = '';
    el('location_form').style.display = '';
  }

  el('more_link').href = 'javascript:submitForm("");void(0);';

  if (el('popular_list')) {
    // Populate the popular searches list.
    for (var i = 0; i < popularSearches.length; i++) {
      var href = 'javascript:goPopular(' + i + ');void(0);';
      var html = '<a href="' + href + '">' +
          popularSearches[i] + '<' + '\a>';
      el('popular_list').innerHTML += html + '<br>';
    }
  }
  setTextContent(el('location_text'), defaultLocation);

  // Video - temporarily commented out for 9/11 promo
  // el('home_video_placeholder').innerHTML = '<object width="290" height="188"><param name="movie" value="http://www.youtube.com/v/8kfEm7K9fdA&hl=en&fs=1&"></param><param name="allowFullScreen" value="true"></param><param name="allowscriptaccess" value="always"></param><embed src="http://www.youtube.com/v/8kfEm7K9fdA&hl=en&fs=1&" type="application/x-shockwave-flash" allowscriptaccess="always" allowfullscreen="true" width="290" height="188"></embed></object>';
}

function doHomepageChangeLocationClick() {
  el("location_subheader").style.display="none"
  el("location_form").style.display="";
}