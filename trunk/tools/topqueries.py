#!/usr/bin/env python
''' topqueries.py writes a list of top queries '''
import sys, os, getopt
from time import strftime

def main(argv):
  ''' Downloads logs from AppEngine and writes a tsv file of top queries '''
  # read and parse command line options
  try:
    opts, args = getopt.getopt(sys.argv[1:],'a:rf:ud:n:')
  except getopt.GetoptError, err:
    # print help information and exit:
    print str(err) # will print something like "option -a not recognized"
    sys.exit(2)
  
  remove_logs = True
  log_file = False
  days = 7
  custom_appcfg_path = False
  num_records = 100
  for opt, arg in opts:
    if opt == "-a":
      custom_appcfg_path = arg
    elif opt == "-r":
      remove_logs = False
    elif opt == "-f":
      log_file = arg
    elif opt == "-d":
      days = arg
    elif opt == "-n":
      num_records = arg
    elif opt == "-u":
      # print usage
      print "./topqueries.py \n \
\t Downloads log files (or reads from disk) and parses the top queries \n \
options:\n \
\t-a [path to appcfg.py if not autolocated]\n \
\t-r (don't automatically delete the raw logs when we're done)\n \
\t-f [file to read logs from directly from disk]\n \
\t-d [# of days to download logs, default 7]\n \
\t-n [# of top queries to return, default 100]"
      sys.exit()
    else:
      assert False, "unhandled option"
    
  # Find appcfg.py (only if we're downloading logs)
  appcfg_path = False
  if not log_file:
    appcfg_paths = []
    if custom_appcfg_path:
      appcfg_paths.append(custom_appcfg_path)
    appcfg_paths += ["/Applications/GoogleAppEngineLauncher.app/Contents/Resources/GoogleAppEngine-default.bundle/Contents/Resources/google_appengine/",
                    "", "../", "../google_appengine/", "../../", "../../google_appengine"]
    for path in appcfg_paths:
      if os.path.exists(path + "appcfg.py"):
        appcfg_path = path
    if not appcfg_path:
      print "ERROR: could not find appcfg.py in any directory, try using -a to specify the location"
      sys.exit()

  if log_file == False:
    # Download the logs from AppEngine    
    os.system("python " + appcfg_path + \
              "appcfg.py request_logs ../frontend/ logs -n " + str(days))
    log_file = "logs"
  
  # Parse the logs to get the query strings
  infile = open(log_file,'r')
  queries = {}
  for entry in infile.readlines():
    if entry.count("/ui_snippets?q=") > 0:
      start = entry.find("/ui_snippets?q=")+15
      end = entry.find("&num=", start)
      query = entry[start:end]
      query = query.lower().strip()
      while query.count("  ") > 0: # remove excess interior whitespace
        query = query.replace("  "," ")
      if query.count('&') == 0: # removes occasional improper URLs
        if query in queries:
          queries[query] += 1
        else:
          queries[query] = 1
  infile.close()
  
  # Delete the log file unless we're told not to
  if remove_logs:
    os.remove(log_file)
  
  # Sort the queries by count
  sorted_queries = sorted(queries.items(), key=lambda (k, v): (v, k))
  sorted_queries.reverse()
  
  # Write top 100 queries to tsv file
  filename = 'top-queries-'+strftime("%Y-%m-%d-%H-%M-%S")+'.tsv'
  outfile = open(filename,'w')
  for query in sorted_queries[:int(num_records)]:
    outfile.write(query[0] + '\t' + str(query[1]) + '\n')
  outfile.close()
  print 'Top queries written to ' + filename + '\n'
  
if __name__ == "__main__":
  main(sys.argv[1:])
