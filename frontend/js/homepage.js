
function runSnippetsQuery() {
  var loc = $.cookie('user_vol_loc');
  if (!loc) {
    loc = geoplugin_city() + ', ' + geoplugin_region();
  }

  var vol_loc = '';
  if (loc) {
    $('#location').val(loc);
    vol_loc = '&vol_loc=' + encodeURIComponent(loc);
    $.cookie('user_vol_loc', loc, {expires: 30});
  }

  var url = '/ui_snippets?start=0&num=15&minimal_snippets_list=1' + vol_loc;
  jQuery.ajax({
    url: url,
    async: true,
    dataType: 'html',
    error: function(){},
    success: function(data){
      el('snippets').innerHTML = data;
      // set up Share links
      var i = 0, link = null;
      while ((link = el('shareable_' + i))) {
        if (link) {
          addthis.button('#share_' + i, 
           {username: 'footprint2009dev', 
            services_compact: 'email, twitter, facebook, myspace, friendfeed, bebo', 
            ui_click: true 
           }, 
           {title: link.innerHTML, url: link.href, 
            templates: {twitter: '{{' + link.href + '}} via www.allforgood.org'}
           });
        }
        i++;
      } 

      // Load analytics, done here to ensure search is finished first
      // Only loading for homepage here - loaded in search_resuls.js
      // for search pages and base.html for static pages
      loadGA();
      $('#col1, #col2, #col3').equalHeightColumns();
    }
  });
}

function updateTweets() {
  var url = '/proxy?url=' 
          + encodeURIComponent('http://twitter.com/statuses/user_timeline/34344129.rss');

  jQuery.ajax({
    url: url,
    async: true,
    dataType: 'xml',
    error: function(){},
    success: function(data){
      var xml = data;
      var html = new Array();
      var title_max = 66;

      var n = 0;
      $(xml).find('item').each(function(){
        if ((n++) < 3) {
          var twt = $(this).find('title').text();
          var ar = twt.split(':');
          var tweeter = ar.shift();
          var title = ar.join(':');
          var link = $(this).find('link').text();
          var ago = 'a litle while';
          var now = (new Date()).getTime();
          try {
            var unit = '';
            var then = (new Date(Date.parse($(this).find('pubDate').text()))).getTime();
            var dt = Math.round((now - then) / 1000);
            if (dt < 60) {
              unit = 'second';
            } else if (dt < 3600) {
              dt = Math.round(dt / 60);
              unit = 'minute';
            } else if (dt < (24 * 3600)) { 
              dt = Math.round(dt / 3600);
              unit = 'hour';
            } else if (dt < (14 * 24 * 3600)) { 
              dt = Math.round(dt / (24 * 3600));
              unit = 'day';
            } else {
              dt = Math.round(dt / (7 * 24 * 3600));
              unit = 'week';
            }
            ago = dt + ' ' + unit + (dt == 1 ? '' : 's');
          } catch(err) {
          }
          html.push('<li', (n == 1 ? ' class="first"' : (n == 3 ? ' class="last"' : '')), '>');
          html.push('<a target="_blank" href="', link, '">', tweeter, ':</a> ');
          html.push(title.substr(0, title_max), (title.length > title_max ? '...' : ''));
          html.push(' <span style="white-space:nowrap;">', ago, ' ago</span>');
          html.push('</li>');
        }
      });
      
      $('#tweets').html(html.join(''));
      $('#col1, #col2, #col3').equalHeightColumns();
    }
  });
}
