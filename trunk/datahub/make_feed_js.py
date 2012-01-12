#!/usr/bin/python

import os
import sys
import urllib
import socket
import subprocess

import pipeline_keys

"""
  processed       2011-12-12 13:09:40
  elapsed 39
  bytes   104483022
  numopps 35583
  expired 13568
  badlinks        0
  numorgs 18830
  noloc   0
  dups    149
  ein501c3        9425
  proper_name     United Way
"""

def make_row(processed, elapsed, bytes, numorgs, numopps, expired, badlinks, noloc, dups, ein501c3):

  js = ("  new Array('%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s')" %
          (processed, elapsed, bytes, numorgs, numopps, expired, badlinks, noloc, dups, ein501c3))
  csv = ('"%s", "%s", "%s", "%s", "%s", "%s", "%s", "%s", "%s", "%s"' %
          (processed, elapsed, bytes, numorgs, numopps, expired, badlinks, noloc, dups, ein501c3))

  return js, csv


def make_detail_file(processed, feed_file):

  # claim the last set of details for this processing time
  ts = str(processed).replace('-', '').replace(':', '').replace(' ', '')
  for detail in ['badlinks', 'duplicates', 'expired', 'nolocation']:
    last_file = feed_file.replace('-history.txt', '-' + detail + '-last.txt')
    if os.path.isfile(last_file):
      detail_file = feed_file.replace('-history.txt', '-' + ts + '-' + detail + '.txt')
      os.rename(last_file, detail_file)
      if pipeline_keys.PRIMARY_WEB_NODE.find(socket.gethostname()) < 0:
        cmd = 'scp -q %s %s/feeds/' % (detail_file, pipeline_keys.PRIMARY_WEB_NODE)
        subprocess.call(cmd, shell=True)

  
def make_js_and_csv(subdir = 'feeds'):

  for dirname, dirnames, filenames in os.walk(subdir):
    for filename in filenames:
      feed_file = os.path.join(dirname, filename)
      if not feed_file.endswith('-history.txt'):
        continue
  
      fh = open(feed_file, 'r')
      if fh:
        out = []
        csv = []
        lines = fh.readlines()
        processed = numorgs = numopps = expired = badlinks = dups = noloc = ein501c3 = proper_name = ''
        for line in lines:
          line = line.rstrip()
          #print line
          if line.startswith('processed\t'):
            ar = line.split('.')
            ar = ar[0].split('\t')
            if processed:
              js_str, csv_str = make_row(processed, elapsed, bytes, numorgs, numopps, 
                                         expired, badlinks, noloc, dups, ein501c3)
              out.append(js_str)
              csv.append(csv_str)

            last_processed = processed = ar[1]
            numorgs = numopps = expired = badlinks = dups = noloc = ein501c3 = ''
          elif line.startswith('elapsed\t'):
            ar = line.split('\t')
            elapsed = ar[1]
          elif line.startswith('numorgs\t'):
            ar = line.split('\t')
            numorgs = ar[1]
          elif line.startswith('numopps\t'):
            ar = line.split('\t')
            numopps = ar[1]
          elif line.startswith('bytes\t'):
            ar = line.split('\t')
            bytes = ar[1]
          elif line.startswith('expired\t'):
            ar = line.split('\t')
            expired = ar[1]
          elif line.startswith('badlinks\t'):
            ar = line.split('\t')
            badlinks = ar[1]
          elif line.startswith('noloc\t'):
            ar = line.split('\t')
            noloc = ar[1]
          elif line.startswith('dups\t'):
            ar = line.split('\t')
            dups = ar[1]
          elif line.startswith('ein501c3\t'):
            ar = line.split('\t')
            ein501c3 = ar[1]
          elif line.startswith('proper_name\t'):
            ar = line.split('\t')
            proper_name = ar[1]
  
        if processed:
          last_processed = processed
          js_str, csv_str = make_row(processed, elapsed, bytes, numorgs, numopps, 
                                     expired, badlinks, noloc, dups, ein501c3)
          out.append(js_str)
          csv.append(csv_str)

        fh.close()

        out.append('  null);')
        js = 'var procs = new Array(\n' + ',\n'.join(out)
        js += "\nvar provider_proper_name = '" + proper_name + "';\n"
        js_file = feed_file.replace('.txt', '.js.ing')
        fh = open(js_file, 'w')
        if fh:
          fh.write(js + '\n')
          fh.close()
          os.rename(js_file, js_file.replace('.ing', ''))

        # claim the last set of details for this processing time
        if last_processed:
          make_detail_file(last_processed, feed_file)

        rows = ('"processed", "elapsed", "bytes", "numorgs", "numopps"' 
              + '"expired, "badlinks", "noloc, "dups, "ein501c3"' 
              + '\n' + '\n'.join(csv))
        csv_file = feed_file.replace('.txt', '.csv.ing')
        fh = open(csv_file, 'w')
        if fh:
          fh.write(rows + '\n')
          fh.close()
          os.rename(csv_file, csv_file.replace('.ing', ''))
  
        out = []
        csv = []

        # make combined versions of the js, csv files
        for ext in ['csv', 'js']:
          if ext == 'js':
            marker = '  new Array('
            ufile = js_file
	    ofile = js_file.replace('-history', '-common')
          else:
            marker = None
            ufile = csv_file
            ofile = csv_file.replace('-history', '-common')

          lines_list = []
          for node in pipeline_keys.WEB_NODES:
            url = node + ufile.replace('.ing', '')

            ufh = None
            try:
              ufh = urllib.urlopen(url)
            except:
              print 'could not open ' + url
              continue

            if ufh:
              lines = ufh.readlines()
              ufh.close()
              if lines:
                lines_list.append(lines)

          if len(lines_list) > 1:
            header = []
            trailer = []
            lines = lines_list[0]

            # both csv, js have one line headers
            header.append(lines[0])
            lines = lines[1:]

            common = []
            for line in lines:
              if not marker or line.find(marker) >= 0:
                common.append(line)
              else:
                trailer.append(line)
           
            lines_list = lines_list[1:]
            for lines in lines_list:
              lines = lines[len(header):]
              for line in lines:
                if not marker or line.find(marker) >= 0:
                  common.append(line)

            unique_lines = []
            for line in header:
              unique_lines.append(line)

            common.sort()
            for line in common:
              if not line in unique_lines:
                unique_lines.append(line)

            for line in trailer:
              unique_lines.append(line)

            fh = open(ofile, 'w')
            if fh:
              fh.write(''.join(unique_lines))
              fh.close()
              os.rename(ofile, ofile.replace('.ing', ''))

              if pipeline_keys.PRIMARY_WEB_NODE.find(socket.gethostname()) < 0:
                ofile = ofile.replace('.ing', '')
                cmd = 'scp -q %s %s/feeds/' % (ofile, pipeline_keys.PRIMARY_WEB_NODE)
                subprocess.call(cmd, shell=True)


def main():
  make_js_and_csv()
  

if __name__ == "__main__":
  main()
