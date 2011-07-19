#!/usr/bin/php
<?php
$max = 0;
ini_set("allow_url_fopen", 1);

$arFields = Array(
  "id" => "",
  "feed_providername" => "girlscouts",
  "feedid" => "139",
  "feed_providerid" => "girlscouts",
  "feed_providerurl" => "http://www.girlscouts.org/",
  "feed_description" => "Girls Scouts",
  "feed_createddatetime" => @date("Y-m-d") . "T00:00:00Z",
  "title" => "Girl Scout Troop Leader; Short Term event or series volunteer",
  "description" => "Girls in the military community are waiting for you! Today, Girls Scouts is about developing leadership skills in girls ages 5-17, so they can have the courage, confidence, and character to make the world a better place. We are looking for volunteers to create a safe, nurturing environment where this can happen.  If you have a skill or interest to share, a passion for helping girls, and some time to commit, there's a place for you in Girl Scouting. Whether you can give a lot of time or just a little, you can make a difference in the lives of girls from military families. Connect with us to talk about what works for you: Troop Leadership One of the most rewarding and popular ways to participate in Girl Scouting is by joining a team to guide a group of girls in a troop setting. As a Girl Scout troop volunteer, you can: -- Form or assist with a troop (of any grade level) at any time of the year -- Schedule troop meetings and events convenient to both the girls' and your volunteer team's schedules (after school, evenings, or weekends) == Receive free orientation, support, and networking opportunities Other Opportunities Volunteering at a two-to six-hour event, helping at a weeklong day camp, sharing a skill at a weekend seminar, or other flexible options.",
  "employer" => "",
  "quantity" => "",
  "image_link" => "",
  "abstract" => "Girls in the military community are waiting for you! Today, Girls Scouts is about developing leadership skills in girls ages 5-17, so they can have the courage, confidence, and character to make the world a better place. We are looking for volunteers to create a safe, nurturing environment where this can happen.  If you have a skill or interest to share, a passion for helping girls, and some time to commit, there's a place for you in Girl Scouting. Whether you can give a lot of time or just a little, you can make a difference in the lives of girls from military families. Connect with us to talk about what works for you",
  "paid" => "False",
  "self_directed" => "False",
  "micro" => "False",
  "detailurl" => "",
  "opportunityid" => "",
  "organizationid" => "",
  "volunteersslots" => "",
  "volunteersfilled" => "",
  "volunteersneeded" => "",
  "minimumage" => "",
  "sexrestrictedto" => "",
  "skills" => "Prospective volunteers must be at least 18 years of age and complete Girl Scouts' application and background-screening process. Volunteers also must become registered Girl Scout members. Financial aid may be available to cover the annual \$12 membership fee.",
  "contactname" => "",
  "contactphone" => "",
  "contactemail" => "",
  "providerurl" => "http://www.girlscouts.org/",
  "language" => "",
  "lastupdated" => "",
  "expires" => "2030-12-31T23:59:59Z",
  "org_nationalein" => "",
  "org_guidestarid" => "",
  "org_name" => "Girls Scouts",
  "org_missionstatement" => "Girl Scouting builds girls of courage, confidence, and character, who make the world a better place.",
  "org_description" => "Girl Scouts of the USA was chartered by the U.S. Congress on March 16, 1950",
  "org_phone" => "",
  "org_fax" => "",
  "org_email" => "",
  "org_organizationurl" => "http://www.girlscouts.org/",
  "org_logourl" => "http://www.girlscouts.org/images/_header/girl_scouts.gif",
  "org_providerurl" => "http://www.girlscouts.org/",
  "categories" => "Vetted",
  "audiences" => "",
  "orglocation" => "",
  "provider_proper_name" => "Girl Scouts",
  "event_date_range" => @date("Y-m-d") . "T00:00:00Z/9999-12-31T23:59:59Z",
  "starttime" => "0",
  "endtime" => "0",
  "ical_recurrence" => "",
  "openended" => "True",
  "duration" => "",
  "commitmenthoursperweek" => "0",
  "virtual" => "False",
  "location" => "",
  "latitude" => "",
  "longitude" => "",
  "location_string" => "",
  "venue_name" => "",
  "eventrangestart" => @date("Y-m-d") . "T00:00:00Z",
  "eventrangeend" => "2030-12-31T23:59:59Z",
  "eventduration" => "365",
  "aggregatefield" => "",
  "randomsalt" => ""
);

function google_geocode($q) {
  $rtn = null;
  $url = "http://maps.google.com/maps/geo"
       . "?q=$q"
       . "&oe=utf-8"
       . "&sensor=false"
       . "&key=ABQIAAAAxq97AW0x5_CNgn6-nLxSrxQuOQhskTx7t90ovP5xOuY_YrlyqBQajVan2ia99rD9JgAcFrdQnTD4JQ";

 
  $delay = 1;
  while (true) {
    $jo = json_decode(implode('', @file($url)));
    if ($jo->{'Status'}->{'code'} == "200") {
      $rtn = $jo->{'Placemark'}[0]->{'Point'}->{'coordinates'};
      break;
    } else if ($jo->{'Status'}->{'code'} == "620") {
      $delay *= 2;
      sleep($delay);
    } else {
      # probably invalid address, i.e. $jo->{'Status'}->{'code'} == "602"
      break;
    }
  }

  return $rtn;
}

foreach ($arFields as $field => $value) {
  echo "$field" . ($field != "randomsalt" ? "\t" : "\n");
}

$arFields["aggregatefield"] = $arFields["title"] . " " . $arFields["description"];

#$lines = file("data-girlscouts.tsv");
#foreach ($lines as $line) {

$arZips = Array();
$fh = fopen("llzip.tsv", 'r');
while (!feof($fh)) {
  $line = trim(fgets($fh));
  $ar = explode("\t", $line);
  $zip = $ar[0];
  $ar = explode(",", str_replace(" ", '', $ar[1]));
  if ($ar[0] == '200') {
    $arZips[$zip] = Array($ar[2], $ar[3]);
  }
}


$fh = fopen("data-girlscouts.tsv", 'r');
while (!feof($fh)) {
  $line = trim(fgets($fh));

  $arValues = explode("\t", $line);
  $latlng = $arZips[$arValues[1]];
  if ($latlng) {
    #$arFields["latitude"] = $latlng[1];
    #$arFields["longitude"] = $latlng[0];
    $arFields["latitude"] = $latlng[0];
    $arFields["longitude"] = $latlng[1];

    $arFields["location_string"] = $arValues[0] . " " . $arValues[1];
    $arFields["location"] = $arValues[1];
    $arFields["detailurl"] = $arValues[2];

    $arFields["id"] = md5($arFields["org_organizationurl"] 
                       .  "\t" . $arFields["event_date_range"]
                       .  "\t" . $arFields["latitude"]
                       .  "\t" . $arFields["longitude"]
                       .  "\t" . $arFields["title"]
                       .  "\t" . $arFields["description"]
                       .  "\t" . $arFields["detailurl"]
                       );

    $arFields["randomsalt"] = rand()/getrandmax();
    foreach ($arFields as $field => $value) {
      echo "$value" . ($field != "randomsalt" ? "\t" : "\n");
    }
  }

  if ($max > 0) {
    $max--;
    if ($max < 1) {
      break;
    }
  }
}

?>
