
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

var arTwitterResponses = new Array();
var arTwitterFeeds = new Array(
  new Array('pointsoflight', 224382700),
  new Array('HandsOnNetwork', 15728184),
  new Array('createthegood', 17999296),
  new Array('servedotgov', 59204932),
  new Array('live_united', 16506355),
  new Array('idealist', 15096075),
  new Array('Habitat_org', 33898911),
  new Array('BetheChangeInc', 11379362),
  new Array('UniversalGiving', 17009647),
  new Array('pamelahawley', 15591578),
  new Array('communitysvc', 121839819),
  new Array('huffpostimpact', 80681990),
  new Array('causecast', 14090017),
  new Array('All_for_Good', 34344129) //last
);

function sort_tweets(a, b) {
  if (a[0] > b[0]) {
    return -1;
  } else if (a[0] < b[0]) {
    return 1;
  } 
  return 0;
}

function processTweets(xml) {
  if (!xml) {
    arTwitterResponses.push(null);
  } else {
    var arTweetList = new Array();
    var title_max = 66;
    var n = 0;
    $(xml).find('item').each(function(){
      if ((n++) < 1) {
        var now = (new Date()).getTime();
        var html = new Array();
        var twt = $(this).find('title').text();
        var ar = twt.split(':');
        var tweeter = ar.shift();
        var title = ar.join(':');
        var link = $(this).find('link').text();
        var ago = 'a litle while';
        var when = null;
        var dt = 0;
        try {
          var unit = '';
          when = (new Date(Date.parse($(this).find('pubDate').text()))).getTime();
          var dt = Math.round((now - when) / 1000);
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
        if (when) {
          html.push('<li class="rotate">');
          html.push('<a target="_blank" href="', link, '">', tweeter, ':</a> ');
          html.push(title.substr(0, title_max), (title.length > title_max ? '...' : ''));
          html.push(' <span style="white-space:nowrap;">', ago, ' ago</span>');
          html.push('</li>');
          arTweetList.push(when, html.join(''));
        }
      }
    });

    if (arTweetList.length > 0) {
      arTwitterResponses.push(arTweetList);
    } else {
      arTwitterResponses.push(null);
    }
  }

  if (arTwitterResponses.length == arTwitterFeeds.length) {
    var ar = new Array();
    for (var i in arTwitterResponses) {
      if (arTwitterResponses[i]) {
        ar.push(arTwitterResponses[i]);
      }
    }

    ar.sort(sort_tweets);

    var arAllTweets = new Array();
    if (ar.length <= 3) {
      for (var i in ar) {
        arAllTweets.push(ar[i]);
      }
    } else {
      var z = ar.length - 1;
      for (var i = 3; i > 0; i--) {
        arAllTweets.push(ar[z - i]);
      }
      for (var i = 0; i < z - 3; i++) {
        arAllTweets.push(ar[i]);
      }
    }

    var html = new Array();
    for (var i in arAllTweets) {
      if (arAllTweets[i]) {
        html.push(arAllTweets[i][1]);
      }
    }

    $('#tweets').html(html.join(''));
    $('#col1, #col2, #col3').equalHeightColumns();
    var r = new Rotator({direction:1,move_delay_ms:1, rotate_delay_ms:8 * 1000});
    r.start(8 * 1000);
  }
}

function fetchTweets(twitter_feed) {
  var url = '/proxy?url=' + encodeURIComponent(twitter_feed);
  jQuery.ajax({
    url: url, async: true, dataType: 'xml',
    error: function(){processTweets(null)},
    success: function(data){processTweets(data)}
  });
}

function updateTweets() {
  for (var i in arTwitterFeeds) {
    if (arTwitterFeeds[i]) {
      // we can't read from twitter directly because they quota against all of appspot.com
      //var url = 'http://twitter.com/statuses/user_timeline/' + arTwitterFeeds[i][1] + '.rss';
      var node = new Array('li169-139', 'li67-22')[Math.floor(2 * Math.random())];
      var url = 'http://' + node + '.members.linode.com/~footprint/twitter/' + arTwitterFeeds[i][1] + '.rss';
      fetchTweets(url);
    }
  }
}
