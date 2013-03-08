#!/usr/bin/python
#

"""
script for processing downloaded feeds
Usage: pipeline.py 
"""

import os
import sys
import re
import gzip
import bz2
import time
from datetime import datetime
import random
import commands
import subprocess

from dateutil import parser
from dateutil import relativedelta

import logging
import optparse

import providers
import pipeline_keys

from csv import DictReader, DictWriter, excel_tab, register_dialect, QUOTE_NONE

import footprint_lib
import xml_helpers as xmlh
import check_links

HOMEDIR = "/home/footprint/allforgood-read-only/datahub"
LOGPATH = HOMEDIR + "/dashboard.ing/"
FEEDSDIR = "feeds"

#
BAD_LINKS = {}
RECHECK_BAD_LINKS = False

# if you rename these remember that the dashboard has to be updated first...
LOG_FN = "load_gbase.log"
LOG_FN_BZ2 = "load_gbase.log.bz2"
DETAILED_LOG_FN = "load_gbase_detail.log"

# TODO: this file needs to be copied over to frontend/autocomplete/
POPULAR_WORDS_FN = "popular_words.txt"
FIELD_STATS_FN = "field_stats.txt"
FIELD_HISTOGRAMS_FN = "field_histograms.txt"

STOPWORDS = set([
  'a', 'about', 'above', 'across', 'after', 'afterwards', 'again', 'against',
  'all', 'almost', 'alone', 'along', 'already', 'also', 'although', 'always',
  'am', 'among', 'amongst', 'amoungst', 'amount', 'an', 'and', 'another', 'any',
  'anyhow', 'anyone', 'anything', 'anyway', 'anywhere', 'are', 'around', 'as',
  'at', 'back', 'be', 'became', 'because', 'become', 'becomes', 'becoming',
  'been', 'before', 'beforehand', 'behind', 'being', 'below', 'beside',
  'besides', 'between', 'beyond', 'bill', 'both', 'bottom', 'but', 'by', 'call',
  'can', 'cannot', 'cant', 'co', 'computer', 'con', 'could', 'couldnt', 'cry',
  'de', 'describe', 'detail', 'do', 'done', 'down', 'due', 'during', 'each',
  'eg', 'eight', 'either', 'eleven', 'else', 'elsewhere', 'empty', 'enough',
  'etc', 'even', 'ever', 'every', 'everyone', 'everything', 'everywhere',
  'except', 'few', 'fifteen', 'fify', 'fill', 'find', 'fire', 'first', 'five',
  'for', 'former', 'formerly', 'forty', 'found', 'four', 'from', 'front','full',
  'further', 'get', 'give', 'go', 'had', 'has', 'hasnt', 'have', 'he', 'hence',
  'her', 'here', 'hereafter', 'hereby', 'herein', 'hereupon', 'hers', 'herself',
  'him', 'himself', 'his', 'how', 'however', 'hundred', 'i', 'ie', 'if', 'in',
  'inc', 'indeed', 'interest', 'into', 'is', 'it', 'its', 'itself', 'keep',
  'last', 'latter', 'latterly', 'least', 'less', 'ltd', 'made', 'many', 'may',
  'me', 'meanwhile', 'might', 'mill', 'mine', 'more', 'moreover', 'most',
  'mostly', 'move', 'much', 'must', 'my', 'myself', 'name', 'namely', 'neither',
  'never', 'nevertheless', 'next', 'nine', 'no', 'nobody', 'none', 'noone',
  'nor', 'not', 'nothing', 'now', 'nowhere', 'of', 'off', 'often', 'on', 'once',
  'one', 'only', 'onto', 'or', 'other', 'others', 'otherwise', 'our', 'ours',
  'ourselves', 'out', 'over', 'own', 'part', 'per', 'perhaps', 'please', 'put',
  'rather', 're', 'same', 'see', 'seem', 'seemed', 'seeming', 'seems',
  'serious', 'several', 'she', 'should', 'show', 'side', 'since', 'sincere',
  'six', 'sixty', 'so', 'some', 'somehow', 'someone', 'something', 'sometime',
  'sometimes', 'somewhere', 'still', 'such', 'system', 'take', 'ten', 'than',
  'that', 'the', 'their', 'them', 'themselves', 'then', 'thence', 'there',
  'thereafter', 'thereby', 'therefore', 'therein', 'thereupon', 'these', 'they',
  'thick', 'thin', 'third', 'this', 'those', 'though', 'three', 'through',
  'throughout', 'thru', 'thus', 'to', 'together', 'too', 'top', 'toward',
  'towards', 'twelve', 'twenty', 'two', 'un', 'under', 'until', 'up', 'upon',
  'us', 'very', 'via', 'was', 'we', 'well', 'were', 'what', 'whatever', 'when',
  'whence', 'whenever', 'where', 'whereafter', 'whereas', 'whereby', 'wherein',
  'whereupon', 'wherever', 'whether', 'which', 'while', 'whither', 'who',
  'whoever', 'whole', 'whom', 'whose', 'why', 'will', 'with', 'within',
  'without', 'would', 'yet', 'you', 'your', 'yours', 'yourself', 'yourselves',
  # custom stopwords for footprint
  'url', 'amp', 'quot', 'help', 'http', 'search', 'nbsp', 'need', 'cache',
  'vol', 'housingall', 'wantedall', 'personalsall', 'net', 'org', 'www',
  'gov', 'yes', 'no', '999',
  ])

OPTIONS = None
FILENAMES = None

class our_dialect(excel_tab):
  """Dialect used for Solr CSV files. """
  quotechar = ''
  quoting = QUOTE_NONE
register_dialect('our-dialect', our_dialect)

def get_delta_days(date_delta):
  """Add up the days, months and years to get the total number of days."""
  return date_delta.days + \
         (date_delta.months * 30) + \
         (date_delta.years * 365)

def get_options():
  """Generates command-line options."""
  global OPTIONS, FILENAMES
  parser = optparse.OptionParser()

  # Standard options
  parser.add_option('-b', '--use_base', action='store_true', default=False,
                    dest='use_base',
                    help='Update the Base index. Can be used with --use_solr.')
  parser.add_option('-s', '--use_solr', action='store_true', default=False,
                    dest='use_solr',
                    help='Update the Solr index. Can be used with --use_base.')
  parser.add_option('-t', '--test_mode', action='store_true', default=False,
                    dest='test_mode',
                    help='Don\'t process or upload the data files')
  # Base options
  base_group = parser.add_option_group("Google Base options")
  base_group.add_option('--base_ftp_user',
                        default=pipeline_keys.BASE_FTP_USER,
                        dest='base_ftp_user',
                        help ='GBase username')
  base_group.add_option('--base_ftp_pass',
                        default=pipeline_keys.BASE_FTP_PASS,
                        dest='base_ftp_pass',
                        help ='GBase password')
  base_group.add_option('--base_cust_id',
                        default=pipeline_keys.BASE_CUSTOMER_ID,
                        dest='base_cust_id',
                        help ='GBase customer ID.')
  # Solr options
  solr_group = parser.add_option_group("Solr options")
  solr_group.add_option('--solr_url',
                        default=pipeline_keys.SOLR_URLS,
                        dest='solr_urls',
                        action='append',
                        help ='URL of a Solr instance to be updated. ' + \
                              'This option may be used multiple times.')
  solr_group.add_option('--solr_user',
                        default=pipeline_keys.SOLR_USER,
                        dest='solr_user',
                        help ='Solr username.')
  solr_group.add_option('--solr_pass',
                        default=pipeline_keys.SOLR_PASS,
                        dest='solr_pass',
                        help ='Solr password')

  solr_group.add_option('--feed_providername',
                        default=None,
                        dest='feed_providername')
  (OPTIONS, FILENAMES) = parser.parse_args()


def print_progress(msg):
  """print progress message-- shutup pylint"""
  print str(datetime.now())+": "+msg

KNOWN_WORDS = {}
def process_popular_words(content):
  """update the dictionary of popular words."""
  # TODO: handle phrases (via whitelist, then later do something smart.
  print_progress("cleaning content: %d bytes" % len(content))
  cleaner_regexp = re.compile('<[^>]*>', re.DOTALL)
  # Overwrite content to save RAM.
  content = re.sub(cleaner_regexp, '', content).lower()
  print_progress("splitting words, %d bytes" % len(content))
  # Iterate words rather than allocating several million of them at once.
  for wordmatch in re.finditer(r'([a-zA-Z0-9]+)', content):
    word = wordmatch.group(1)
    # ignore common english words
    if word in STOPWORDS:
      continue
    # ignore short words
    if len(word) <= 2:
      continue
    if word not in KNOWN_WORDS:
      KNOWN_WORDS[word] = 0
    KNOWN_WORDS[word] += 1

  print_progress("cleaning rare words from %d words" % len(KNOWN_WORDS))
  for word in KNOWN_WORDS.keys():
    if KNOWN_WORDS[word] < 2:
      del KNOWN_WORDS[word]

  print_progress("done: word dict size %d words" % len(KNOWN_WORDS))

def print_word_stats():
  """dump word stats."""
  print_progress("final cleanse: keeping only words appearing 10 times")
  for word in KNOWN_WORDS.keys():
    if KNOWN_WORDS[word] < 10:
      del KNOWN_WORDS[word]
  sorted_words = list(KNOWN_WORDS.iteritems())
  sorted_words.sort(cmp=lambda a, b: cmp(b[1], a[1]))

  print_progress("writing "+POPULAR_WORDS_FN+"...")
  popfh = open(LOGPATH+POPULAR_WORDS_FN, "w")
  for word, freq in sorted(sorted_words):
    popfh.write(str(freq)+"\t"+word+"\n")
  popfh.close()
  print_progress("done writing "+LOGPATH+POPULAR_WORDS_FN)

FIELD_VALUES = None
FIELD_NAMES = None
NUM_RECORDS_TOTAL = 0

# 
LATLNG_HISTOGRAM = {}
# key = number of days in the future
STARTDATE_HISTOGRAM = {}
# key = hour of the day, GMT
STARTHOUR_HISTOGRAM = {}
# length in days
DURATION_HISTOGRAM = {}

def process_field_stats(content):
  """update the field-value histograms."""
  global FIELD_NAMES, FIELD_VALUES, NUM_RECORDS_TOTAL
  for lineno, line in enumerate(content.splitlines()):
    fields = line.split("\t")
    if lineno == 0:
      if FIELD_NAMES == None:
        FIELD_NAMES = fields
        FIELD_VALUES = [{} for i in range(len(fields))]
      continue
    NUM_RECORDS_TOTAL += 1
    lat_val = lng_val = event_date_range = start_time = None
    for i, val in enumerate(fields):
      if lat_val is None and FIELD_NAMES[i].find('latitude') >= 0:
        lat_val = val
      elif lng_val is None and FIELD_NAMES[i].find('longitude') >= 0:
        lng_val = val
      elif event_date_range is None and FIELD_NAMES[i].find('event_date_range') >= 0:
        event_date_range = val
      val = val[0:300]
      if val in FIELD_VALUES[i]:
        FIELD_VALUES[i][val] += 1
      else:
        FIELD_VALUES[i][val] = 1
    lat_fltval = float(lat_val)
    if lat_fltval > 500.0:
      lat_fltval -= 1000.0
    lng_fltval = float(lng_val)
    if lng_fltval > 500.0:
      lng_fltval -= 1000.0
    lat_val = re.sub(r'([.]\d\d)\d+', r'\1', str(lat_fltval))
    lng_val = re.sub(r'([.]\d\d)\d+', r'\1', str(lng_fltval))
    latlng = lat_val + ',' + lng_val
    if latlng in LATLNG_HISTOGRAM:
      LATLNG_HISTOGRAM[latlng] += 1
    else:
      LATLNG_HISTOGRAM[latlng] = 1
    # 2010-01-01T00:00:00/2010-04-15T00:00:00
    match = re.search(r'(....-..-..)T(..):..:../(....-..-..)T(..):..:..',
                      event_date_range)
    if match:
      start_date = match.group(1)
      start_hour = match.group(2)
      end_date = match.group(3)
      if start_date in STARTDATE_HISTOGRAM:
        STARTDATE_HISTOGRAM[start_date] += 1
      else:
        STARTDATE_HISTOGRAM[start_date] = 1
      if start_hour in STARTHOUR_HISTOGRAM:
        STARTHOUR_HISTOGRAM[start_hour] += 1
      else:
        STARTHOUR_HISTOGRAM[start_hour] = 1
      duration = (datetime.strptime(end_date, "%Y-%m-%d") -
                  datetime.strptime(start_date, "%Y-%m-%d"))
      duration_days = duration.days
      if duration_days > 365:
        duration_days = 365
      if duration_days in DURATION_HISTOGRAM:
        DURATION_HISTOGRAM[duration_days] += 1
      else:
        DURATION_HISTOGRAM[duration_days] = 1

def print_field_stats():
  """dump field-value stats."""
  print_progress("writing "+FIELD_STATS_FN+"...")
  outfh = open(LOGPATH+FIELD_STATS_FN, "w")
  outfh.write("number of records: "+str(NUM_RECORDS_TOTAL)+"\n")
  if FIELD_NAMES:
    for i, fieldname in enumerate(FIELD_NAMES):
      outfh.write("field "+fieldname+":uniqvals="+str(len(FIELD_VALUES[i]))+"\n")
      sorted_vals = list(FIELD_VALUES[i].iteritems())
      sorted_vals.sort(cmp=lambda a, b: cmp(b[1], a[1]))
      for val, freq in sorted_vals[0:1000]:
        if freq < 10:
          break
        outfh.write("  %5d %s\n" % (freq, val))
    outfh.close()
  print_progress("done writing "+FIELD_STATS_FN)

def print_field_histograms():
  print_progress("writing "+FIELD_HISTOGRAMS_FN+"...")
  outfh = open(LOGPATH+FIELD_HISTOGRAMS_FN, "w")
  outfh.write("latlong histogram:\n")
  for val, freq in LATLNG_HISTOGRAM.iteritems():
    outfh.write("%s %d\n" % (str(val), freq))
  outfh.write("start_date histogram:\n")
  for val, freq in STARTDATE_HISTOGRAM.iteritems():
    outfh.write("%s %d\n" % (str(val), freq))
  outfh.write("start_hour histogram:\n")
  for val, freq in STARTHOUR_HISTOGRAM.iteritems():
    outfh.write("%s %d\n" % (str(val), freq))
  outfh.write("duration histogram:\n")
  for val, freq in DURATION_HISTOGRAM.iteritems():
    outfh.write("%s %d\n" % (str(val), freq))
  outfh.close()
  print_progress("done writing "+FIELD_HISTOGRAMS_FN)

def append_log(outstr):
  """append to the detailed and truncated log, for stats collection."""
  outfh = open(LOGPATH+DETAILED_LOG_FN, "a")
  outfh.write(outstr)
  outfh.close()

  outfh = open(LOGPATH+LOG_FN, "a")
  for line in outstr.split('\n'):
    if re.search(r'(STATUS|ERROR)', line):
      outfh.write(line+"\n")
  outfh.close()

  # create a bzip2 file from the log
  infh = open(LOGPATH+LOG_FN, "r")
  data = infh.read()
  infh.close()
  outfh = bz2.BZ2File(LOGPATH+LOG_FN_BZ2, "w")
  outfh.write(data)
  outfh.close()

def error_exit(msg):
  """Print an error message to stderr and exit."""
  print >> sys.stderr, msg
  sys.exit(1)

# Use a shell for subcommands on Windows to get a PATH search.
USE_SHELL = sys.platform.startswith("win")
def solr_update_query (query_str, url):
  """Queries the Solr backend specified via the command line args."""
  cmd = 'curl -s -u \'' + OPTIONS.solr_user + ':' + OPTIONS.solr_pass + \
        '\' \'' + url + \
        'update?commit=true\' --data-binary ' + \
        '\'' + query_str + '\'' \
        ' -H \'Content-type:text/plain; charset=utf-8\';'

  subprocess.call(cmd, shell=True)


def run_shell_with_retcode(command, print_output=False, universal_newlines=True):
  """Executes a command and returns the output from stdout and the return code.

  Args:
    command: Command to execute.
    print_output: If True, the output is printed to stdout.
                  If False, both stdout and stderr are ignored.
    universal_newlines: Use universal_newlines flag (default: True).

  Returns:
    Tuple (output, return code)
  """
  logging.info("Running %s", command)
  proc = subprocess.Popen(command, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          shell=USE_SHELL,
                          universal_newlines=universal_newlines)
  if print_output:
    output_array = []
    while True:
      line = proc.stdout.readline()
      if not line:
        break
      print line.strip("\n")
      output_array.append(line)
    output = "".join(output_array)
  else:
    output = proc.stdout.read()
  proc.wait()
  errout = proc.stderr.read()
  if print_output and errout:
    print >> sys.stderr, errout
  proc.stdout.close()
  proc.stderr.close()
  append_log(output)
  append_log(errout)
  return output, errout, proc.returncode


def run_shell(command, silent_ok=False, universal_newlines=True,
              print_output=False):
  """run a shell command."""
  print " ".join(command)
  stdout, stderr, retcode = run_shell_with_retcode(command, print_output,
                                                   universal_newlines)
  #if retcode and retcode != 0:
  #error_exit("Got error status from %s:\n%s\n%s" % (command, stdout, stderr))
  if not silent_ok and not stdout:
    error_exit("No output from %s" % command)
  return stdout, stderr, retcode


def run_pipeline(name, url, do_processing=True, do_ftp=True):
  """shutup pylint."""

  start_time = datetime.now()
  print_progress("loading "+name+" from "+url)

  feed_file_size = 0
  if os.path.isfile(url):
    feed_file_size = os.path.getsize(url)

  # run as a subprocess so we can ignore failures and keep going.
  # later, we'll run these concurrently, but for now we're RAM-limited.
  # ignore retcode
  # match the filenames to the feed filenames in Google Base, so we can
  # manually upload for testing.
  tsv_filename = name+"1.gz"
  if not re.search(r'^https?://', url) and not os.path.exists(url):
    print_progress('Feed file missing: ' + url)
    return

  if do_processing:
    cmd_list = ["./footprint_lib.py"]

    if OPTIONS.feed_providername:
      for it in ["--feed_providername", OPTIONS.feed_providername]:
        cmd_list.append(it)

    for it in ["--progress", "--output", tsv_filename, url, "--compress_output"]:
      cmd_list.append(it)

    if name == "diy":
      cmd_list.append("--noclean")

    stdout, stderr, retcode = run_shell(cmd_list, silent_ok=True, print_output=False)
    print stdout,

    if stderr and stderr != "":
      print name+":STDERR: ", re.sub(r'\n', '\n'+name+':STDERR: ', stderr)

    if retcode and retcode != 0:
      print name+":RETCODE: "+str(retcode)

  print_progress("reading TSV data...")

  try:
    gzip_fh = gzip.open(tsv_filename, 'r')
    tsv_data = gzip_fh.read()
    gzip_fh.close()
  except:
    print_progress("Warning: %s could not be read." % tsv_filename)
    return

  if len(tsv_data) == 0:
    print_progress("Warning: TSV file is empty.")
    return

  #if OPTIONS.use_solr:
  #  #print_progress('creating Solr tsv file')
  #  create_solr_TSV(name+'1', start_time, feed_file_size)
  create_solr_TSV(name+'1', start_time, feed_file_size)


def test_loaders():
  """for testing, read from local disk as much as possible."""
  run_pipeline("americanredcross", "americanredcross.xml", False, False)
  run_pipeline("mlk_day", "mlk_day.xml", False, False)
  run_pipeline("gspreadsheets",
               "https://spreadsheets.google.com/ccc?key=rOZvK6aIY7HgjO-hSFKrqMw",
               False, False)
  run_pipeline("craigslist", "craigslist-cache.txt", False, False)


def loaders():
  """put all loaders in one function for easier testing."""

  for name in [
               "handsonnetworkconnect",
               #DEV "handsonnetworkconnect_dev",
               # handsonnetworkconnect_dev is only for DEV server 
               #DEPRECATED "handsonnetwork1800", 
               # 12/1 moved to handsonconnect
               #DEPRECATED "handsonnetworktechnologies", 
               # can stop processing legacy HON feed 10/12/2011
               #DEPRECATED "handsonnetwork", 
               "unitedway", 
               "daytabank", 
               # need to contact feed provider 2011-11-16
               "mentorpro", 
               "aarp", 
               "americanredcross", 
               # need to contact feed provider 2011-11-12
               #"americansolutions",
               "americorps", 
               "christianvolunteering", 
               # need to contact feed provider 2011-11-12
               #"1sky", 
               # commented on 1/29/2013 "sparked", 
               "citizencorps", 
               # need to contact feed provider 2011-11-12
               #"extraordinaries", 
               "givingdupage",
               "greentheblock", 
               "habitat", 
               # need to contact feed provider 2011-11-12
               #"mlk_day", 
               # need to contact feed provider 2011-11-12
               #"myproj_servegov", 
               "newyorkcares", 
               "rockthevote", 
               "threefiftyorg", 
               "catchafire",
               # need to contact feed provider 2011-11-12
               #"servenet", 
               "servicenation",
               "universalgiving", 
               "volunteergov", 
               "up2us",
               # need to contact feed provider 2011-11-12
               #"volunteertwo", 
               # need to contact feed provider 2011-11-12
               #"washoecounty", 
               "getinvolved",
               # commented on 1/29/2013 "ymca", 
               "uso",
               "seniorcorps",
               "usaintlexp",
               "samaritan",
               # moved idealist down in order of feeds 10/12/2011
               "idealist", 
               ]:

    if not FILENAMES or name in FILENAMES:
      run_pipeline(name, name + ".xml")

  if not FILENAMES or "diy" in FILENAMES:
    run_pipeline("diy", "diy.tsv")

  if FILENAMES:
    for file in FILENAMES:
      if re.search('updateHON', file):
	theFileName = file.replace('./HONupdates/','')
        theFileName = file.replace('.xml','')
        run_pipeline(theFileName, file)
        # run_pipeline("updateHON", file)

  # requires special crawling
  # This next block triggers the processing of the google sheets.
  # The sheet parameter is from a deprecated sheet and it won't be processed
  # in reality it will only process the sheets that are listed in ./spreadsheets/process.py
  if not FILENAMES or "gspreadsheets" in FILENAMES:
    run_pipeline("gspreadsheets",
                 "https://spreadsheets.google.com/ccc?key=rOZvK6aIY7HgjO-hSFKrqMw")

  # if we ever want to try craigslist again, uncomment these
  # note: craiglist crawler is run asynchronously, hence the local file
  #if not FILENAMES or "craigslist" in FILENAMES:
  #  run_pipeline("craigslist", "craigslist-cache.txt")


def ftp_to_base(filename, ftpinfo, instr):
  """ftp the string to base, guessing the feed name from the orig filename."""
  print_progress("attempting to FTP " + filename + " to base")
  ftplib = __import__('ftplib')
  stringio = __import__('StringIO')

  dest_fn = footprint_lib.guess_shortname(filename)
  if dest_fn == "":
    dest_fn = "footprint1.txt"
  else:
    dest_fn = dest_fn + "1.gz"

  if re.search(r'[.]gz$', dest_fn):
    print_progress("compressing data from "+str(len(instr))+" bytes")
    gzip_fh = gzip.open(dest_fn, 'wb', 9)
    gzip_fh.write(instr)
    gzip_fh.close()
    data_fh = open(dest_fn, 'rb')
  else:
    data_fh = stringio.StringIO(instr)

  host = 'uploads.google.com'
  (user, passwd) = ftpinfo.split(":")
  print_progress("connecting to " + host + " as user " + user + "...")
  ftp = ftplib.FTP(host)
  welcomestr = re.sub(r'\n', '\\n', ftp.getwelcome())
  print_progress("FTP server says: "+welcomestr)
  ftp.login(user, passwd)
  print_progress("uploading filename "+dest_fn)
  success = False
  while not success:
    try:
      ftp.storbinary("STOR " + dest_fn, data_fh, 8192)
      success = True
    except:
      # probably ftplib.error_perm: 553: Permission denied on server. (Overwrite)
      print_progress("upload failed-- sleeping and retrying...")
      time.sleep(1)
      ftp = ftplib.FTP(host)
      welcomestr = re.sub(r'\n', '\\n', ftp.getwelcome())
      print_progress("FTP server says: "+welcomestr)
      ftp.login(user, passwd)
      print_progress("uploading filename "+dest_fn)
  if success:
    print_progress("done uploading.")
  else:
    print_progress("giving up.")
  ftp.quit()
  data_fh.close()

  
# row dictionary reference
# see rowdictionaryreference.txt

def solr_retransform(fname, start_time, feed_file_size):
  """Create Solr-compatible versions of a datafile"""
  numopps = 0

  print_progress('Creating Solr transformed file for: ' + fname)
  out_filename = fname + '.transformed'
  data_file = open(fname, "r")
  try:
    csv_reader = DictReader(data_file, dialect='our-dialect')
    csv_reader.next()
  except:
    print data_file.read()
    print_progress("error processing %s" % str(fname))
    return

  shortname = footprint_lib.guess_shortname(fname)
  if not shortname:
    shortname = fname

  fnames = csv_reader.fieldnames[:]
  fnames.append("c:eventrangestart:dateTime")
  fnames.append("c:eventrangeend:dateTime")
  fnames.append("c:eventduration:integer")
  fnames.append("c:aggregatefield:string")
  fnames.append("c:dateopportunityidgroup:string")
  fnames.append("c:randomsalt:float")
  fnamesdict = dict([(x, x) for x in fnames])

  data_file = open(fname, "r")
  # TODO: Switch to TSV - Faster and simpler
  csv_reader = DictReader(data_file, dialect='our-dialect')
  csv_writer = DictWriter(open (out_filename, 'w'),
                          dialect='excel-tab',
                          fieldnames=fnames)
  for field_name in fnamesdict.keys():
    fnamesdict[field_name] = fnamesdict[field_name].lower()
    if fnamesdict[field_name].startswith('c:'):
      fnamesdict[field_name] = fnamesdict[field_name].split(':')[1]

  csv_writer.writerow(fnamesdict)
  now = parser.parse(commands.getoutput("date"))
  today = now.date()
  expired_by_end_date = num_bad_links = 0
  for rows in csv_reader:
    if rows["title"] and rows["title"].lower().find('anytown museum') >= 0:
      #bogus event
      continue

    if not 'c:OpportunityID:string' in rows:
      continue

    # Split the date range into separate fields
    # event_date_range can be either start_date or start_date/end_date
    split_date_range = []
    if rows["event_date_range"]:
      split_date_range = rows["event_date_range"].split('/')

    if split_date_range:
      rows["c:eventrangestart:dateTime"] = split_date_range[0]
      if len(split_date_range) > 1:
        rows["c:eventrangeend:dateTime"] = split_date_range[1]
      else:
        if rows["c:openended:boolean"] == "Yes":
          rows["c:eventrangeend:dateTime"] = rows["c:expires:dateTime"]
        else:
          rows["c:eventrangeend:dateTime"] = rows["c:eventrangestart:dateTime"]

    # in case we somehow got here without already doing this
    rows["title"] = footprint_lib.cleanse_snippet(rows["title"])
    rows["description"] = footprint_lib.cleanse_snippet(rows["description"])
    rows["c:detailURL:URL"] = rows["c:detailURL:URL"].replace("&amp;", '&'); 
    if not rows["c:detailURL:URL"].lower().startswith('http'):
      rows["c:detailURL:URL"] = 'http://' + rows["c:detailURL:URL"]

    link = str(rows["c:detailURL:URL"])
    if link in BAD_LINKS or check_links.is_bad_link(link, RECHECK_BAD_LINKS):
      num_bad_links += 1
      footprint_lib.feed_report(rows['c:OpportunityID:string'], 'badlinks', shortname, link)
      dlink = "'" + str(link) + "'"
      if dlink not in BAD_LINKS:
        BAD_LINKS[dlink] = 0
        print_progress("bad link: " + dlink)
      BAD_LINKS[dlink] += 1
      continue

    rows["c:org_missionStatement:string"] = footprint_lib.cleanse_snippet(
                                               rows["c:org_missionStatement:string"])
    rows["c:org_description:string"] = footprint_lib.cleanse_snippet(
                                               rows["c:org_description:string"])

    rows["c:aggregatefield:string"] = footprint_lib.cleanse_snippet(' '.join([
                                               rows["title"],
                                               rows["description"],
                                               rows["c:provider_proper_name:string"],
                                               rows.get("c:skills:string", rows.get("c:skill:string", '')),
                                               rows.get("c:categoryTags:string", rows.get("c:categoryTag:string", '')),
                                               rows["c:org_name:string"],
                                               rows["c:eventName:string"],
                                               ]))

    ids = rows.get('c:OpportunityID:string', rows.get('c:opportunityID:string', 'OpportunityID'))
    ds = str(rows.get("c:eventrangestart:dateTime", '2001'))
    if ds.find('T') > 0:
      ds = ds.split('T')[0]
    rows["c:dateopportunityidgroup:string"] = ''.join([ds, ids])

    for key in rows.keys():
      if key.find(':dateTime') != -1:
        if rows[key].find(':') > 0:
          rows[key] += 'Z'
      elif key.find(':integer') != -1:
        if rows[key] == '':
          rows[key] = 0
        else:
          # find the first numbers from the string, e.g. abc123.4 => 123
          try:
            rows[key] = int(re.sub(r'^.*?([0-9]+).*$', r'\1', rows[key]))
          except:
            print_progress("error parsing rows[key]=%s -- rejecting record." % str(rows[key]))
            continue

    try:
      start_date = parser.parse(rows["c:eventrangestart:dateTime"], ignoretz=True)
    except:
      start_date = "2001-01-01T00:00:00"

    try:
      end_date = parser.parse(rows["c:eventrangeend:dateTime"], ignoretz=True)
    except:
      end_date = "2020-12-31T23:59:59"

    try:
      # check for expired opportunities
      delta_days = get_delta_days(relativedelta.relativedelta(end_date, today))
      if delta_days < -2 and delta_days > -3000:
        # more than 3000? it's the 1971 thing
        # else it expired at least two days ago
        footprint_lib.feed_report(rows['c:OpportunityID:string'], 'expired', shortname, link)
        expired_by_end_date += 1
        continue

      duration_rdelta = relativedelta.relativedelta(end_date, start_date) 
      duration_delta_days = get_delta_days(duration_rdelta)
    
      # Check whether start/end dates are the wrong way around.
      if duration_delta_days < 0:
        # removing this code for now-- too scary wrt. typos
        # e.g. what happens if 9/11/2009 - 9/7/2009  and it turns out
        # that the 7 was supposed to be a 17 i.e. simple typo-- by
        # swapping you've made it worse.  Correct solution is to add
        # to spreadsheet checker, then reject start>end here.
        # even this is the wrong place to do this-- should apply to
        # both Base and SOLR.
        #print_progress('Date error: start > end. Swapping dates...')
        #duration_delta_days = -duration_delta_days
        #temp = rows["c:eventrangestart:dateTime"]
        #rows["c:eventrangestart:dateTime"] = rows["c:eventrangeend:dateTime"]
        #rows["c:eventrangeend:dateTime"] = temp
        print_progress("start date after end date: rejecting record.")
        continue

      # Fix for events that are ongoing or whose dates were unsucessfully
      # parsed. These events have start and end dates on 0000-01-01.
      #
      # These events get a large eventduration (used for ranking) so that
      # they are not erroneously boosted for having a short duration.
      current_rdelta = relativedelta.relativedelta(today, end_date)
      current_delta_days = get_delta_days(current_rdelta)
      rows["c:eventduration:integer"] = max(duration_delta_days,
                                          current_delta_days)
    except:
      pass

    # GBASE LEGACY: Fix to the +1000 to lat/long hack   
    if not rows['c:latitude:float'] is None and float(rows['c:latitude:float']) > 500:
      rows['c:latitude:float'] = float(rows['c:latitude:float']) - 1000.0
    if not rows['c:longitude:float'] is None and float(rows['c:longitude:float']) > 500:
      rows['c:longitude:float'] = float(rows['c:longitude:float']) - 1000.0

    # The random salt is added to the result score during ranking to prevent
    # groups of near-identical results with identical scores from appearing
    # together in the same result pages without harming quality.
    rows["c:randomsalt:float"] = str(random.uniform(0.0, 1.0))

    csv_writer.writerow(rows)
    numopps += 1

  data_file.close()
  print_progress("bad links: %d" % num_bad_links)
  print_progress("  expired: %d" % expired_by_end_date)


  # NOTE: if you change this, you also need to update datahub/load_gbase.py
  # and frontend/views.py to avoid breaking the dashboard-- other status
  # messages don't matter.
  elapsed = datetime.now() - start_time
  xmlh.print_status("done parsing: output " + str(footprint_lib.NUMORGS) + " organizations" +
                    " and " + str(numopps) + " opportunities" +
                    " (" + str(feed_file_size) + " bytes): " +
                    str(int(elapsed.seconds/60)) + " minutes.",
                    shortname)

  proper_name = shortname
  if shortname in providers.ProviderNames:
    proper_name = providers.ProviderNames[shortname].get('name', shortname)

  # do the per-provider summary
  if shortname:
    processed = str(datetime.now()).split('.')[0]
    
    try:
      fh = open(FEEDSDIR + '/' + shortname + '-last.txt', 'r')
    except:
      fh = None
      footprint_stats = None

    if fh:
      footprint_stats = fh.read()
      fh.close()

    fh = open(FEEDSDIR + '/' + shortname + '-history.txt', 'a')
    if fh:
      fh.write('processed\t' + processed + '\n')
      fh.write('elapsed\t' + str(int(elapsed.seconds/60)) + '\n')
      fh.write('bytes\t' + str(feed_file_size) + '\n')
      fh.write('numopps\t' + str(numopps) + '\n')
      fh.write('expired\t' + str(expired_by_end_date) + '\n')
      fh.write('badlinks\t' + str(num_bad_links) + '\n')
      if footprint_stats:
        fh.write(footprint_stats)
      fh.write('proper_name\t' + proper_name + '\n')
      fh.close()

  return out_filename


def create_solr_TSV(filename, start_time, feed_file_size):
  """ Transform FPXML to SOLR TSV """
  in_fname = filename + '.gz'
  f_out = open(filename, 'wb')
  f_in = gzip.open(in_fname, 'rb')

  f_out.writelines(f_in)
  f_out.close()
  f_in.close()

  solr_filename = solr_retransform(filename, start_time, feed_file_size)


def main():
  """ program starts here """
#  solr_filename = solr_retransform('handsonnetworkconnect1', datetime.now(), 6563535)
  #solr_filename = create_solr_TSV('handsonnetworkconnect1', datetime.now(), 6563535)
#  run_pipeline("unitedway", "unitedway.xml")
  #sys.exit(0)
                                                                                                  
  get_options()

  if OPTIONS.test_mode:
    global LOGPATH
    LOGPATH = "./"
    test_loaders()
  else:
    loaders()

  #print_word_stats()
  #print_field_stats()
  #print_field_histograms()

if __name__ == "__main__":
  main()
