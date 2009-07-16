''' usage: python topqueries.py [path_to_appcfg.py] '''
import sys, os
from time import strftime

def main(argv):
  ''' Downloads logs from AppEngine and writes a tsv file of top queries '''
  # Download the logs from AppEngine
  appcfg_path = "/Applications/GoogleAppEngineLauncher.app/Contents/Resources/GoogleAppEngine-default.bundle/Contents/Resources/google_appengine/"
  if len(sys.argv) > 1:
    appcfg_path = sys.argv[1]
  os.system("python " + appcfg_path + \
            "appcfg.py request_logs ../frontend/ logs -n 7")
  
  # Parse the logs to get the query strings
  infile = open('logs','r')
  queries = {}
  for entry in infile.readlines():
    if entry.count("/ui_snippets?q=") > 0:
      start = entry.find("/ui_snippets?q=")+15
      end = entry.find("&num=", start)
      query = entry[start:end]
      if query.count('&') == 0: # removes occasional improper URLs
        if query in queries:
          queries[query] += 1
        else:
          queries[query] = 1
  infile.close()
  
  # Sort the queries by count
  sorted_queries = sorted(queries.items(), key=lambda (k, v): (v, k))
  sorted_queries.reverse()
  
  # Write top 100 queries to tsv file
  filename = 'top-queries-'+strftime("%Y-%m-%d-%H-%M-%S")+'.tsv'
  outfile = open(filename,'w')
  for query in sorted_queries[:100]:
    outfile.write(query[0] + '\t' + str(query[1]) + '\n')
  outfile.close()
  print 'Top queries written to ' + filename + '\n'
  
if __name__ == "__main__":
  main(sys.argv[1:])
