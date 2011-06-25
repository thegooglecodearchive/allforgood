<?php
  ini_set("allow_url_fopen", "1");
  if (empty($category)) {
    $category = $_GET["category"];
  }
  if (empty($action)) {
    $action = $_GET["action"];
  }
  if (empty($label)) {
    $label = $_GET["label"];
  }
  

  #$GA_DOMAIN = "http://" . $_SERVER["SERVER_NAME"];
  $GA_DOMAIN = "http://www.allforgood.org";
  // Copyright 2009 Google Inc. All Rights Reserved.
  #$GA_ACCOUNT = "GA-8689219-2";
  $GA_ACCOUNT = "MO-8689219-2";
  $GA_PIXEL = "http://li169-139.members.linode.com/~footprint/ga.php";

  function googleAnalyticsGetImageUrl() {
    global $GA_ACCOUNT, $GA_PIXEL;
    global $category, $action, $label;
    $url = "";
    $url .= $GA_PIXEL . "?";
    $url .= "utmac=" . $GA_ACCOUNT;
    $url .= "&utmn=" . rand(0, 0x7fffffff);

    $referer = $_SERVER["HTTP_REFERER"];
    $query = $_SERVER["QUERY_STRING"];
    $path = $_SERVER["REQUEST_URI"];

    if (empty($referer)) {
      $referer = "-";
    }
    $url .= "&utmr=" . urlencode($referer);

    if (!empty($path)) {
      $url .= "&utmp=" . urlencode($path);
    }

    $url .= "&guid=ON";
    $url .= "&category=$category";
    $url .= "&action=$action";
    $url .= "&label=$label";
    #$url .= "&utmdebug=1";

    #return str_replace("&", "&amp;", $url);
    return $url;
  }

  $googleAnalyticsImageUrl = googleAnalyticsGetImageUrl();
  #echo '<img src="' . $googleAnalyticsImageUrl . '" />';
  #echo "$googleAnalyticsImageUrl";
  
  header("Content-Type: image/gif");
  readfile($googleAnalyticsImageUrl);
?>
