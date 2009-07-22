#!/usr/bin/env python
''' tagging.py takes in a list of *1.gz files to read, tags them based on 
tagger classes found in taggers.py, and writes them to *2.gz files '''
import sys
import gzip
from csv import reader, writer
from taggers import KeywordTagger, SimpleKeywordTagger
import time
import random

def tag_listings(fname):
  ''' this is run for each file that is tagged, opens *1.gz, runs each row
  through all taggers, and exports to *2.gz '''
  # open fname1.gz for reading
  infile = gzip.open(fname+"1.gz", 'rb')
  inreader = reader(infile, dialect='excel-tab')
  
  # open fname2.gz for writing
  outfile = gzip.open(fname+"2.gz", 'wb')
  outwriter = writer(outfile, dialect='excel-tab')
  
  fields = inreader.next()
  outwriter.writerow(fields) #add the header row unchanged
  
  # Get list of tagger instances
  taggers = get_taggers(fields)
  
  # run each row through each tagger using the doTagging() function defined
  # in the Tagger base class
  for row in inreader:
    for tagger in taggers:
      row = tagger.do_tagging(row)
    outwriter.writerow(row)

  infile.close()
  outfile.close()

def get_taggers(fields):
  ''' returns the current tagger instances we're using '''
  # Determine the columns for title, description, and categories
  title_col = fields.index('title')
  descr_col = fields.index('description')
  tag_col = fields.index('c:categories:string')
  
  # Create basic keyword taggers

  # The taggers below use the SimpleKeywordTagger to easily tag without
  # creating a dict with individual scores for each keyword.  The commented
  # code below shows how to create a standard KeywordTagger when we're
  # ready to assign individual scores

  # nature_tagger = KeywordTagger('Nature', {'environment':1.0, 'nature':1.0, \
  # 'environmental':1.0, 'outdoors':1.0, 'gardening':1.0, 'garden':1.0, \
  # 'park':1.0, 'wetlands':1.0,'forest':1.0, 'trees':1.0}, \
  # [title_col, descr_col], tag_col)

  nature_tagger = SimpleKeywordTagger('Nature', 'environment nature \
  environmental outdoors gardening garden park wetlands forest forests \
  tree trees green trail trails sierra+club ', [title_col, descr_col], tag_col)
  
  education_tagger = SimpleKeywordTagger('Education','education reading \
  teaching teacher teach books book library literacy school schools libraries \
  classroom class',[title_col, descr_col], tag_col)
  
  animals_tagger = SimpleKeywordTagger('Animals','animal animals dog dogs cat \
  cats zoo bird birds zoos',
  [title_col, descr_col], tag_col)
  
  health_tagger = SimpleKeywordTagger('Health','health hospital hospitals \
  medical healthcare mental hospice nursing cancer nurse nurses doctor doctors\
  red+cross',
  [title_col, descr_col], tag_col)
  
  seniors_tagger = SimpleKeywordTagger('Seniors','senior seniors elderly',
  [title_col, descr_col], tag_col)
  
  technology_tagger = SimpleKeywordTagger('Technology','website computer \
  computers technology web video graphic design',
  [title_col, descr_col], tag_col)
  
  hph_tagger = SimpleKeywordTagger('Homelessness Poverty & Hunger','habitat \
  homeless hunger food housing poverty house poor',[title_col, descr_col], tag_col)
  
  tutoring_tagger = SimpleKeywordTagger('Tutoring','mentoring \
  tutoring mentor counseling', [title_col, descr_col], tag_col)
      
  # taggers is the list of Tagger subclass instances ot run each row through
  taggers = [nature_tagger, education_tagger, animals_tagger, health_tagger, \
  seniors_tagger, technology_tagger, hph_tagger, tutoring_tagger]
  
  return taggers

def show_tags(fname):
  ''' simple testing function to check the number of items tagged, 
  will not be in final code '''
  infile = gzip.open(fname+"2.gz", 'rb')
  inreader = reader(infile, dialect='excel-tab')

  taggers = get_taggers(inreader.next())
  tag_stats = {'Total Rows':0, 'Tagged':0}
  for tagger in taggers:
    tag_stats[tagger.tag_name] = 0

  for row in inreader:
    tag_stats['Total Rows'] += 1
    for tagger in taggers:
      if row[42].count(tagger.tag_name) > 0:
        tag_stats[tagger.tag_name] += 1
    if row[42]:
      tag_stats['Tagged'] += 1

    # print a random 1% of tagged data for inspection
    if random.random() < 0.01:
      print row[7], "- Tags:", row[42]
      print row[8]
      print

  print tag_stats
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

