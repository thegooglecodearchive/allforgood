#!/usr/bin/php
<?php
ini_set('allow_url_fopen', 1);
chdir('/home/footprint/allforgood-read-only/datahub/spreadsheets');

$gdoc_key = '0Av2uzfMXJ8MvdDVWSkZNMGczbGZIN3VBNmpaaDJvV2c';

define('TIMESTAMP', 'Timestamp');
define('NAME', 'Your name');
define('EMAIL', 'Your email address');
define('ORG', 'Name of your organization or group');
define('PHONE', 'Your phone number');
define('AGREED', 'By submitting your listings, you agree to the terms and conditions of All for Good as well as the Content License Agreement found at http://www.allforgood.org/cla');
define('PID', 'provider id (reference)');
define('SHEET_URL', 'Spreadsheet URL');
define('VETTED', 'vetted');
define('NOTIFIED', 'notified');

$list_url = "https://docs.google.com/spreadsheet/pub?key=$gdoc_key&single=true&gid=0&output=txt";

$url = $list_url . "&cb=" . rand();
system('wget -q -O list.tsv "' . $url . '"');
$arLines = file('list.tsv');
$arHeader = null;

function getField($col, $row) {
  global $arHeader;

  foreach ($arHeader as $idx=>$hdr_col) {
    if ($hdr_col == $col) {
      return $row[$idx];
    }
  }

  return '';
}

function getKeyValue($url) {
  $rtn = '';
  $ar = explode('key=', $url);
  if (count($ar) > 1) {
    $ar = explode('&', $ar[1]);
    $ar = explode('#', $ar[0]);
    $rtn = $ar[0];
  }
  return $rtn;
}

foreach ($arLines as $line) {
  $line = rtrim($line);
  if ($arHeader == null) {
    $arHeader = explode("\t", $line);
  } else {
    $arCells = explode("\t", $line);
    $agreed = getField(AGREED, $arCells);
    $sheet = getField(SHEET_URL, $arCells);
    if ($agreed == 'Agree' && strpos($sheet, 'http') != 0) {
      $timestamp = getField(TIMESTAMP, $arCells);
      $row_key = rawurlencode($timestamp);
      $url = "http://staging.servicefootprint.appspot.com";
      $url .= "/oppsform?row=$row_key";
      $nRetries = 0;
      while ($nRetries < 3) {
        echo "$url\n";
        $arRsp = file($url);
        foreach($arRsp as $line) {
          echo $line;
        }
        if (strpos($arRsp[0], 'retry') == 0) {
          $nRetries++;
          sleep(3);
        } else {
          break;
        }
      }
    }
  }
}

# now get any we may have added
$url = $list_url . "&cb=" . rand();
system('wget -q -O list.tsv "' . $url . '"');
$arLines = file('list.tsv');
$arHeader = null;

$py = "# this file is automatically generated\n";
$py .= "sheet_list = [\n";

foreach ($arLines as $line) {
  $line = trim($line);
  if ($arHeader == null) {
    $arHeader = explode("\t", $line);
  } else {
    $arCells = explode("\t", $line);
    $url = getField(SHEET_URL, $arCells);
    if (strpos($url, 'http') == 0) {
      $id = getKeyValue($url);
      if (!empty($id)) {
        $org = str_replace("'", '', getField(ORG, $arCells));
        $pid = str_replace("'", '', getField(PID, $arCells));
        if ($pid < 1 ) {
          $pid = $last_pid + 1;
        }
        $py .= "  {'id' : '$id',\n";
        $py .= "   'org' : '$org', 'pid' : '$pid',\n";
        $py .= "  },\n";
        $last_pid = $pid;
      }
    }
  }
}

$py .= "]\n";

$fh = fopen('process.py', 'w');
fwrite($fh, $py);
fclose($fh);


