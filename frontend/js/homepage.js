
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
        }
      });
}
