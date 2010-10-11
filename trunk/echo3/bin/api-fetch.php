#!/usr/local/bin/php
<?php
#http://www.allforgood.org/api/volopps?key=superman&q=education&start=1&num=200&dump=1&output=rss
if( strlen($_SERVER["SERVER_PORT"])<1 && is_array($argv) ) {
  # there are 2 possibilities... cli and URL
  # if this is a URL and we really don't want
  # to do this
  foreach( $argv as $arg) {
    $ar = explode("=",$arg);
    if( count($ar)>1 ) {
      $var = $ar[0];
      $value = $ar[1];
      ${$var} = "$value";
    }
  }
}

ini_set("allow_url_fopen", 1);

if (!isset($start)) {
  $start = 1;
}

if (!isset($step)) {
  $step = 200;
}

if (!isset($api_key)) {
  $api_key = "superman";
}

if (!isset($q)) {
  $q = "category:education -feedprovider_name:meetup -craigslist";
}

$q = urlencode($q);

if (!isset($vol_dist)) {
  $vol_dist = 1500;
}

$url = "http://www.allforgood.org/api/volopps?key=$api_key"
     . "&q=$q&start=$start&num=$step&vol_dist=$vol_dist&dump=1&output=rss";

$buff = @file_get_contents($url);
$p1 = strrpos($buff, "</channel></rss>");
if ($p1 < 0) {
  die(1);
}
$p0 = strpos($buff, "<item>");
if ($p0 < 0) {
  $p0 = $p1;
}
$intro = substr($buff, 0, $p0);
$items = substr($buff, $p0, $p1 - $p0);
$outro = substr($buff, $p1);
echo "$intro\n$items\n$outro\n";
die(0);
?>
