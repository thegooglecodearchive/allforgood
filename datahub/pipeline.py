#!/usr/bin/env python
#

"""
script for loading into googlebase.
Usage: pipeline.py username password
"""

import sys
import re
import gzip
import bz2
import commands
from dateutil import parser
from dateutil import relativedelta
import logging
import optparse
import os
import pipeline_keys
import random
import subprocess
import time
from csv import DictReader, DictWriter, excel_tab, register_dialect, QUOTE_NONE
from datetime import datetime
import footprint_lib

LOGPATH = "/home/footprint/public_html/datahub/dashboard/"

# rename these-- but remember that the dashboard has to be updated first...
LOG_FN = "load_gbase.log"
LOG_FN_BZ2 = "load_gbase.log.bz2"
DETAILED_LOG_FN = "load_gbase_detail.log"

# this file needs to be copied over to frontend/autocomplete/
POPULAR_WORDS_FN = "popular_words.txt"
FIELD_STATS_FN = "field_stats.txt"
GEO_STATS_FN = "geo_stats.txt"

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

OPTIONS = None
def get_options():
  """Generates command-line options."""
  global OPTIONS
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
  (OPTIONS, args) = parser.parse_args()
  
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
  print_progress("loading words")
  # Iterate words rather than allocating several million of them at once.
  for wordmatch in re.finditer(r'([a-zA-Z0-9])+', content):
    word = wordmatch.group(0)
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
LATLNG_DENSITY = {}
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
    lat_val = lng_val = None
    for i, val in enumerate(fields):
      if lat_val is None and FIELD_NAMES[i].find('latitude') >= 0:
        lat_val = val
      if lng_val is None and FIELD_NAMES[i].find('longitude') >= 0:
        lng_val = val
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
    if latlng in LATLNG_DENSITY:
      LATLNG_DENSITY[latlng] += 1
    else:
      LATLNG_DENSITY[latlng] = 1

def print_field_stats():
  """dump field-value stats."""
  print_progress("writing "+FIELD_STATS_FN+"...")
  outfh = open(LOGPATH+FIELD_STATS_FN, "w")
  outfh.write("number of records: "+str(NUM_RECORDS_TOTAL)+"\n")
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

def print_geo_stats():
  print_progress("writing "+GEO_STATS_FN+"...")
  outfh = open(LOGPATH+GEO_STATS_FN, "w")
  for latlng, freq in LATLNG_DENSITY.iteritems():
    outfh.write("%s %d\n" % (latlng, freq))
  outfh.close()
  print_progress("done writing "+GEO_STATS_FN)

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

def run_shell_with_retcode(command, print_output=False,
                           universal_newlines=True):
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
  stdout, stderr, retcode = run_shell_with_retcode(command, print_output,
                                                   universal_newlines)
  #if retcode and retcode != 0:
  #error_exit("Got error status from %s:\n%s\n%s" % (command, stdout, stderr))
  if not silent_ok and not stdout:
    error_exit("No output from %s" % command)
  return stdout, stderr, retcode

def run_pipeline(name, url, do_processing=True, do_ftp=True):
  """shutup pylint."""
  print_progress("loading "+name+" from "+url)

  # run as a subprocess so we can ignore failures and keep going.
  # later, we'll run these concurrently, but for now we're RAM-limited.
  # ignore retcode
  # match the filenames to the feed filenames in Google Base, so we can
  # manually upload for testing.
  tsv_filename = name+"1.gz"
  if not os.path.exists(url):
    print_progress('Feed file missing: ' + url)
    return
  if do_processing:
    stdout, stderr, retcode = run_shell(["./footprint_lib.py", "--progress",
                                         "--output", tsv_filename, url,
                                         "--compress_output" ],
                                        silent_ok=True, print_output=False)
    print stdout,
    if stderr and stderr != "":
      print name+":STDERR: ", re.sub(r'\n', '\n'+name+':STDERR: ', stderr)
    if retcode and retcode != 0:
      print name+":RETCODE: "+str(retcode)

  print "reading TSV data..."
  gzip_fh = gzip.open(tsv_filename, 'r')
  tsv_data = gzip_fh.read()
  gzip_fh.close()

  print "processing field stats..."
  process_field_stats(tsv_data)

  print "processing popular words..."
  process_popular_words(tsv_data)

  if OPTIONS.use_base and do_ftp:
    print_progress("ftp'ing to base")
    footprint_lib.PROGRESS = True
    ftp_to_base(name,
                OPTIONS.base_ftp_user+":"+OPTIONS.base_ftp_pass,
                tsv_data)
    print_progress("pipeline: done.")
  if OPTIONS.use_solr:
    print_progress('Commencing Solr index updates')
    update_solr_index(name+'1')

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
  run_pipeline("aarp", "aarp.xml")
  run_pipeline("americanredcross", "americanredcross.xml")
  run_pipeline("americansolutions", "americansolutions.xml")
  run_pipeline("americorps", "americorps.xml")
  run_pipeline("christianvolunteering", "christianvolunteering.xml")
  run_pipeline("citizencorps", "citizencorps.xml")
  run_pipeline("extraordinaries", "extraordinaries.xml")
  run_pipeline("givingdupage", "givingdupage.xml")
  run_pipeline("habitat", "habitat.xml")
  run_pipeline("handsonnetwork", "handsonnetwork.xml")
  run_pipeline("idealist", "idealist.xml")
  run_pipeline("meetup", "meetup.xml")
  run_pipeline("mentorpro", "mentorpro.xml")
  run_pipeline("mlk_day", "mlk_day.xml")
  run_pipeline("mybarackobama", "mybarackobama.xml")
  run_pipeline("myproj_servegov", "myproj_servegov.xml")
  run_pipeline("seniorcorps", "seniorcorps.xml")
  run_pipeline("servenet", "servenet.xml")
  run_pipeline("unitedway", "unitedway.xml")
  run_pipeline("volunteergov", "volunteergov.xml")
  run_pipeline("volunteermatch", "volunteermatch.xml")
  run_pipeline("volunteertwo", "volunteertwo.xml")
  run_pipeline("ymca", "ymca.xml")

  # requires special crawling
  run_pipeline("gspreadsheets",
               "https://spreadsheets.google.com/ccc?key=rOZvK6aIY7HgjO-hSFKrqMw")

  # note: craiglist crawler is run asynchronously, hence the local file
  run_pipeline("craigslist", "craigslist-cache.txt")

  # out for launch
  # run_pipeline("mybarackobama",
  #            "http://my.barackobama.com/page/event/search_results?"+
  #            "format=footprint")

  # old custom feed
  # legacy-- to be safe, remove after 9/1/2009
  #run_pipeline("idealist", "http://feeds.idealist.org/xml/feeds/"+
  #           "Idealist-VolunteerOpportunity-VOLUNTEER_OPPORTUNITY_TYPE."+
  #           "en.open.atom.gz")

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
  
def solr_retransform(fname):
  """Create Solr-compatible versions of a datafile"""
  print_progress('Creating Solr transformed file for: ' + fname)
  out_filename = fname + '.transformed'
  data_file = open(fname, "r")
  csv_reader = DictReader(data_file, dialect='our-dialect')
  csv_reader.next()
  fnames = csv_reader.fieldnames[:]
  fnames.append("c:eventrangestart:dateTime")
  fnames.append("c:eventrangeend:dateTime")
  fnames.append("c:eventduration:integer")
  fnames.append("c:aggregatefield:string")
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
  for rows in csv_reader:
    # The random salt is added to the result score during ranking to prevent
    # groups of near-identical results with identical scores from appearing
    # together in the same result pages without harming quality.
    rows["c:randomsalt:float"] = str(random.uniform(0.0, 1.0))
    
    # Split the date range into separate fields
    # event_date_range can be either start_date or start_date/end_date
    split_date_range = rows["event_date_range"].split('/')
    rows["c:eventrangestart:dateTime"] = split_date_range[0]
    if len(split_date_range) > 1:
      rows["c:eventrangeend:dateTime"] = split_date_range[1]
    else:
      rows["c:eventrangeend:dateTime"] = rows["c:eventrangestart:dateTime"]

    rows["c:aggregatefield:string"] = ' '.join([rows["description"],
                                               rows["c:org_name:string"],
                                               rows["title"],
                                               rows["c:categories:string"]])
    for key in rows.keys():
      # Fix to the "double semicolons instead of commas" Base hack.
      rows[key] = rows[key].replace(';;', ',')

      if key.find(':dateTime') != -1:
        rows[key] += 'Z'
      elif key.find(':integer') != -1:
        if rows[key] == '':
          rows[key] = 0
        else:
          rows[key] = int(rows[key])

    start_date = parser.parse(rows["c:eventrangestart:dateTime"], ignoretz=True)
    end_date = parser.parse(rows["c:eventrangeend:dateTime"], ignoretz=True)

    duration_rdelta = relativedelta.relativedelta(end_date, start_date) 
    duration_delta_days = get_delta_days(duration_rdelta)
    
    # Check whether start/end dates are the wrong way around.
    if duration_delta_days < 0:
      print_progress('Date error: start > end. Swapping dates...')
      duration_delta_days = -duration_delta_days
      temp = rows["c:eventrangestart:dateTime"]
      rows["c:eventrangestart:dateTime"] = rows["c:eventrangeend:dateTime"]
      rows["c:eventrangeend:dateTime"] = temp

    # Fix for events that are ongoing or whose dates were unsucessfully
    # parsed. These events have start and end dates on 1971-01-01.
    #
    # These events get a large eventduration (used for ranking) so that
    # they are not erroneously boosted for having a short duration.
    current_rdelta = relativedelta.relativedelta(today, end_date)
    current_delta_days = get_delta_days(current_rdelta)
    rows["c:eventduration:integer"] = max(duration_delta_days,
                                          current_delta_days)

    # Fix to the +1000 to lat/long hack   
    if not rows['c:latitude:float'] is None:
      rows['c:latitude:float'] = float(rows['c:latitude:float']) - 1000.0
    if not rows['c:longitude:float'] is None:
      rows['c:longitude:float'] = float(rows['c:longitude:float']) - 1000.0
    csv_writer.writerow(rows)

  data_file.close()
  return out_filename
  
def update_solr_index(filename):
  """Transform a datafile and update the specified backend's index"""
  in_fname = filename + '.gz'
  f_out = open(filename, 'wb')
  f_in = gzip.open(in_fname, 'rb')
  
  f_out.writelines(f_in)
  f_out.close()
  f_in.close()
  
  solr_filename = solr_retransform(filename)
  for solr_url in OPTIONS.solr_urls:
    print_progress('Uploading file to ' + solr_url)
    # HTTP POST an index update command to Solr and commit changes.
    upload_solr_file(solr_filename, solr_url)

def upload_solr_file(filename, url):
  """ Updates the Solr index with a CSV file """
  cmd = 'curl -s -u \'' + OPTIONS.solr_user + ':' + OPTIONS.solr_pass + \
        '\' \'' + url + \
        'update/csv?commit=true&separator=%09&escape=%10\' --data-binary @' + \
        filename + \
        ' -H \'Content-type:text/plain; charset=utf-8\';'
  subprocess.call(cmd, shell=True)

def main():
  """shutup pylint."""
  get_options()

  if OPTIONS.test_mode:
    global LOGPATH
    LOGPATH = "./"
    test_loaders()
  else:
    loaders()
    if OPTIONS.use_solr:
      for solr_url in OPTIONS.solr_urls:
        print_progress('Post-processing SOLR instance at: ' + solr_url)       
        solr_update_query(
          '<delete><query>expires:[* TO NOW-1DAY]</query></delete>',
          solr_url)
        print_progress('Removed expired documents.')

        solr_update_query('<optimize/>', solr_url)
        print_progress('Optimized index.')

  print_word_stats()
  print_field_stats()
  print_geo_stats()

if __name__ == "__main__":
  main()
