#!/usr/bin/env python
''' topqueries.py writes a list of top queries '''
import sys, os, getopt
from time import strftime

def main(argv):
  ''' Downloads logs from AppEngine and writes a tsv file of top queries '''
  # read and parse command line options
  try:
    opts, args = getopt.getopt(sys.argv[1:],'a:kf:hd:n:y:',["appcfg-path=","keep-logs","log-file=","num-days=","num-records=","help","app-yaml-path="])
  except getopt.GetoptError, err:
    # print help information and exit:
    print str(err) # will print something like "option -a not recognized"
    sys.exit(2)
  
  remove_logs = True
  log_file = False
  days = 7
  custom_appcfg_path = False
  num_records = 100
  custom_app_yaml_path = False
  for opt, arg in opts:
    if opt in ("-a","--appcfg-path"):
      custom_appcfg_path = arg
    elif opt in("-y","--app-yaml-path"):
      custom_app_yaml_path = arg
    elif opt in ("-k","--keep-logs"):
      remove_logs = False
    elif opt in ("-f","--log-file"):
      log_file = arg
    elif opt in ("-d","--num-days"):
      days = arg
    elif opt in ("-n","--num-records"):
      num_records = arg
    elif opt in ("-h","--help"):
      # print usage
      print "./topqueries.py \n \
\t Downloads log files (or reads from disk) and parses the top queries \n \
options:\n \
\t--appcfg-path : path to appcfg.py if not autolocated\n \
\t--app-yaml-path : path to app.yaml if not autolocated\n \
\t--keep-logs : don't automatically delete the raw logs when we're done\n \
\t--log-file : file to read logs from disk (don't download)\n \
\t--num-days : # of days to download logs, default 7\n \
\t--num-records : # of top queries to return, default 100"
      sys.exit()
    else:
      assert False, "unhandled option"
    
  # Find app.yaml (only if we're downloading logs)
  app_yaml_path = False
  if not log_file:
    app_yaml_paths = []
    if custom_app_yaml_path:
      appcfg_paths.append(custom_app_yaml_path)
      appcfg_paths.append(custom_app_yaml_path[:-1])
    app_yaml_paths += ["../frontend",".","","frontend"]
    for path in app_yaml_paths:
      if os.path.exists(path + "/app.yaml"):
        app_yaml_path = path
        print "Found app.yaml in " + path
    if not app_yaml_path:
      print "ERROR: could not find app.yaml in any directory, try using --app-yaml-path= to specify the location"
      sys.exit()
      
  # Find appcfg.py (only if we're downloading logs)
  appcfg_path = False
  if not log_file:
    appcfg_paths = []
    if custom_appcfg_path:
      appcfg_paths.append(custom_appcfg_path)
      appcfg_paths.append(custom_appcfg_path + "/")
    appcfg_paths += ["/Applications/GoogleAppEngineLauncher.app/Contents/Resources/GoogleAppEngine-default.bundle/Contents/Resources/google_appengine/",
                    "", "../", "../google_appengine/", "../../", "../../google_appengine"]
    for path in appcfg_paths:
      if os.path.exists(path + "appcfg.py"):
        appcfg_path = path
        print "Found appcfg.py in " + path
    if not appcfg_path:
      print "ERROR: could not find appcfg.py in any directory, try using --appcfg-path= to specify the location"
      sys.exit()

  if log_file == False:
    # Download the logs from AppEngine    
    os.system("python " + appcfg_path + \
              "appcfg.py request_logs " + app_yaml_path + " logs -n " + str(days))
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
