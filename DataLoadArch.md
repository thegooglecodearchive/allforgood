# ETL Pieces for loading data from partners #

## Exchange _listing partner data enters the system_ ##
  * Receive FPXML post
  * Get from external API
  * Manually updated Spreadsheet
  * Crawl site

## Transform _Convert to FPXML if not in that form_ ##
  * Partner specific parsers
  * Field/Category/Organization mappers
  * Spreadsheet reader

## Load _Insert FPXML strucutred data into Data Store_ ##
  * Insert opportunities into SOLR/GoogleBase instance