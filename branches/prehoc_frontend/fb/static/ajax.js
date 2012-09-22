function makeRequest(url, callback) {
  var http_request = null;
  if (window.XMLHttpRequest) { // Mozilla, Safari,...
    http_request = new XMLHttpRequest();
  } else if (window.ActiveXObject) { // IE
    http_request = new ActiveXObject("Microsoft.XMLHTTP");
  }
  if (!http_request) {
    return;
  }
  http_request.onreadystatechange = function() {
    if (http_request.readyState == 4) {
      if (http_request.status == 200) {
        if (!callback) {
          return;
        }
        var txt = http_request.responseText;
        callback(txt);
      }
    }
  };
  try {
    http_request.open('GET', url, true);
  } catch(err) {
    //alert(url);
  }
  http_request.send(null);
}
