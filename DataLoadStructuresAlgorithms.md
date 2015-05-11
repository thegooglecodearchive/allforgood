# Data Load _data structures and algorithms_ #

## High Level Data Path ##
  1. Convert XML to TSV file
  1. Convert TSV file to csv
  1. Transform csv file to another csv file with minimal fields
  1. Upload re-transformed csv file to SOLR
  1. Left with flat data structure of opportunities, most of the FPXML data strucuture stripped out
  1. Primary search field is aggregation of: description, organization name, title, and categories
