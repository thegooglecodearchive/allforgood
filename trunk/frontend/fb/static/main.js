var page = 1;
var items_per_page = 4;
var search_prompt = 'search...';
var loc_prompt = 'Zip';

function _gel(id) {
  return document.getElementById(id);
}

function getValue(id) {
  var rtn = '';
  var it = _gel(id);
  if (it) {
    if (it.options) {
      if (it.selectedIndex >= 0) {
        rtn = it.options[it.selectedIndex].value;
      }
    } else if (it.type == 'checkbox') {
      rtn = (it.checked ? 1 : 0);
    } else if (it.type && 'hiddentext'.indexOf(it.type) >= 0) {
      rtn = (it.value || '');
    } else if (it.type == 'radio') {
      var ar = document.getElementsByName(it.name);
      for (var i in ar) {
        if (ar[i] && ar[i].type == 'radio') {
          if (ar[i].checked) {
            rtn = (ar[i].value || '');
            break;
          }
        }
      }
    } else {
      rtn = it.innerHTML;
    }
  }
  return rtn;
}

function setValue(id, value) {
  var it = _gel(id);
  if (!it) {
    var ar = document.getElementsByName(id);
    if (ar) {
      it = ar[0];
    }
  }

  if (it) {
    if (it.options) {
      for (var i in it.options) {
        if (it.options[i] && it.options[i].value == value) {
          it.options[i].selected = true;
          break;
        }
      }
    } else if (it.type == 'checkbox') {
      it.checked = (value == 'on' || value =='yes' || value == '1' ? true : false);
    } else if (it.type == 'radio') {
      var ar = document.getElementsByName(id);
      for (var i in ar) {
        if (ar[i] && ar[i].type == 'radio') {
          ar[i].checked = (ar[i].value == value ? true : false);
        }
      }
    } else if (it.type == 'text' || it.type == 'hidden') {
      it.value = value;
    } else {
      it.innerHTML = value;
    }
  }
}

function setDisplay(id, value) {
  var it = _gel(id);
  if (it) {
    it.style.display = value;
  }
}

function toggle_view() {
  var it = _gel('view');
  if (it) {
    var view = (it.innerHTML || 'Map');
    setDisplay('mapview', (view == 'Map' ? 'block' : 'none'));
    setDisplay('listview', (view == 'List' ? 'block' : 'none'));
    setDisplay('next-nav', (view == 'Map' ? 'none' : 'block'));
    setDisplay('prev-nav', (view == 'Map' ? 'none' : (page > 1 ? 'block' : 'none')));
    it.innerHTML = (view == 'Map' ? 'List' : 'Map');
  }
}

function format_date(d) {
  var rtn = '';
  if (d && !isNaN(d.getDate())) {
    var day = d.getDate();
    var month = d.getMonth() + 1;
    if (day < 10) {
      day = '0' + day;
    }
    if (month < 10) {
      month = '0' + month;
    }
    var today = new Date();
    if (d.getFullYear() >= today.getFullYear()) {
      rtn = [month, day, d.getFullYear()].join('/');
    }
  }
  return rtn;
}

function handle_list(txt) {
  try {
    json = JSON.parse(txt);
  } catch(err) {
    json = null;
  }

  if (!json) {
    setValue('list', getValue('noresults'));
  } else {
    var n = 0;
    var html = new Array();
    for (var i in json.items) {
      if (json.items[i] && json.items[i].title && json.items[i].description) {
        html.push('<div class="opp">');
        html.push('<a class="opp-title-link" target="_blank" href="', json.items[i].xml_url, '">');
        var title = json.items[i].title;
        if (title.length > 64) {
          title = title.substr(0, 61) + '...';
        }
        html.push('<div class="opp-title">', json.items[i].title, '</div>');
        html.push('</a>');
        html.push('<div class="opp-detail">');

        if (!json.items[i].virtual && json.items[i].location_name) {
          html.push('<span class="opp-location">', json.items[i].location_name, '</span>');
        }

        if (!json.items[i].openEnded) {
          var start_date = '';
          var end_date = '';
          try {
            var t = new Date(json.items[i].startDate.replace(/-/g, '/'));
            start_date = format_date(t);
          } catch(err) {
          }
          try {
            var t = new Date(json.items[i].endDate.replace(/-/g, '/'));
            end_date = format_date(t);
          } catch(err) {
          }

          if (start_date || end_date) {
            if (json.items[i].virtual && json.items[i].location_name) {
              html.push(',');
            }
            html.push(' <span class="opp-dates">');
            if (start_date == end_date) {
              html.push('on ', start_date);
            } else {
              if (start_date) {
                if (!end_date) {
                  html.push('starts ');
                }
                html.push(start_date);
              }
              if (start_date && end_date) {
                html.push(' - ');
              }
              if (end_date) {
                if (!start_date) {
                  html.push('ends ');
                }
                html.push(end_date);
              }
            }
            html.push('</span>');
          }
        }

        var desc = json.items[i].description;
        if (desc.length > 200) {
          desc = desc.substr(0, 197) + '...';
          // TODO: more/less
        }
        html.push('<div class="opp-desc">', desc, '</div>');
        // TODO: make url_short a link
        html.push('<div class="opp-url">', json.items[i].url_short, '</div>');
        html.push('</div>');

        html.push('</div>');
        n++;
      }
    }
    
    if (n > 0) {
      setValue('list', html.join(''));
    } else {
      setValue('list', getValue('noresults'));
    }
  }
}

function in_loc(it, focus) {
  if (focus) {
    it.select();
    if (it.value == loc_prompt) {
      it.value = '';
      it.style.color = '#000000';
    }
  } else {
    if (!it.value) {
      it.value = loc_prompt;
      it.style.color = '#9999cc';
    } else {
      it.style.color = '#000000';
    }
  }
}

function in_search(it, focus) {
  if (focus) {
    it.select();
    if (it.value == search_prompt) {
      it.value = '';
      it.style.color = '#000000';
    }
  } else {
    if (!it.value) {
      it.value = search_prompt;
      it.style.color = '#9999cc';
    }
  }
}

var prefs = ('{{vol_loc|escapejs}}' + '{{vol_dist|escapejs}}' + '{{category|escapejs}}');
function handle_prefs(rsp) {
}

function set_prefs(vol_loc, vol_dist, category) {
  if (prefs != (vol_loc + vol_dist + category)) {
    prefs = (vol_loc + vol_dist + category);
    var url = '/fb/prefs?';
    url += '&user_id=' + encodeURIComponent('{{user_id|escapejs}}');
    url += '&vol_loc=' + encodeURIComponent(vol_loc);
    url += '&vol_dist=' + encodeURIComponent(vol_dist);
    url += '&category=' + encodeURIComponent(category);
    makeRequest(url, handle_prefs);
  }
}

function search() {
  setValue('list', 'Loading...');

  var q = getValue('q');
  q = (q && q != search_prompt ? q : '');
  var cat = (getValue('category') || '');
  q += (cat ? ' ' + (q ? 'AND ' + cat : cat) : '');
  var vol_loc = getValue('location');
  var loc = (vol_loc == loc_prompt ? '' : vol_loc);
  vol_loc = (loc ? loc : geoplugin_latitude() + ',' + geoplugin_longitude());
 
  var vol_dist = '25';
  var stype = '&type=all';
  var rmi = (getValue('range') || 25);
  if (rmi.indexOf('wide') >= 0) {
    stype = '&type=statewide';
  } else {
    vol_dist = (getValue('range') || 25);
  }

  set_prefs(loc, rmi, cat);

  var url = '/api/volopps?output=json';
  url += '&vol_loc=' + encodeURIComponent(vol_loc);
  url += '&vol_dist=' + encodeURIComponent(vol_dist);
  url += stype;
  url += '&q=' + encodeURIComponent(q);
  url += '&sort=eventrangeend';
  url += '&start=' + encodeURIComponent((page - 1) * items_per_page);
  url += '&key=facebook&num=' + items_per_page;
  makeRequest(url, handle_list);
}

function go_page(v) {
  if (v == 0) {
    page = 1;
  } else {
    page += v;
    if (page < 1) {
      page = 1;
    }
  }
  setDisplay('prev-nav', (page > 1 ? 'block' : 'none'));
  search();
}

setValue('q', search_prompt);
setValue('location', ('{{ vol_loc|escapejs }}' || loc_prompt));
in_loc(_gel('location'), false);
setValue('range', '{{ vol_dist|escapejs }}');
setValue('category', '{{ category|escapejs }}');

search();
