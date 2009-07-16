#!/usr/bin/env python
''' tagging.py takes in a list of *1.gz files to read, tags them based on 
tagger classes found in taggers.py, and writes them to *2.gz files '''
import sys
import gzip
from csv import reader, writer
from taggers import EducationTagger, NatureTagger
import time

def tag_listings(fname):
  ''' this is run for each file that is tagged, opens *1.gz, runs each row
  through all taggers, and exports to *2.gz '''
  # open fname1.gz for reading
  infile = gzip.open(fname+"1.gz", 'rb')
  inreader = reader(infile, dialect='excel-tab')
  
  # open fname2.gz for writing
  outfile = gzip.open(fname+"2.gz", 'wb')
  outwriter = writer(outfile, dialect='excel-tab')

  outwriter.writerow(inreader.next()) #add the header row unchanged
  
  # taggers is the list of Tagger subclass instances ot run each row through
  taggers = [NatureTagger(), EducationTagger()]
  
  # run each row through each tagger using the doTagging() function defined
  # in the Tagger base class
  for row in inreader:
    for tagger in taggers:
      row = tagger.do_tagging(row)
    outwriter.writerow(row)

  infile.close()
  outfile.close()

def show_tags(fname):
  ''' simple testing function to check the number of items tagged, 
  will not be in final code '''
  infile = gzip.open(fname+"2.gz", 'rb')
  inreader = reader(infile, dialect='excel-tab')

  inreader.next() #skip the header row
  num_rows = 0
  num_ed = 0
  num_nat = 0
  num_tagged = 0
  for row in inreader:
    num_rows += 1
    if row[42].count("Nature") > 0:
      num_nat += 1
    if row[42].count("Education") > 0:
      num_ed += 1
    if row[42]:
      num_tagged += 1
  print "# Rows:", num_rows
  print "# Tagged:", num_tagged
  print "# Education:", num_ed
  print "# Nature:", num_nat
  infile.close()

def show_mappings(fname):
  ''' function used for development to get a list of fields in the tsvs '''
  infile = gzip.open(fname+"1.gz", 'rb')
  inreader = reader(infile, dialect='excel-tab')

  fields = inreader.next()
  for field in range(0, len(fields)):
    print field, fields[field]

  infile.close()

def main():
  ''' arguments should be filenames to tag, minus '1.gz' 
  Takes each input file and calls tag_listings on it '''
  for arg in sys.argv[1:]:
    print "starting to tag", arg
    start = time.time()
    tag_listings(arg)
    show_tags(arg)
    end = time.time()
    print arg, "tagged in", end-start, "seconds"
    print
    
if __name__ == "__main__":
  main()

