# Data Store Architecture #

## Key points ##
  * SOLR instance
  * No complex types
  * Flat table of volunteer opportunities
  * Single point of failure
    * Not cloud based
    * Manual intervention required to failover to backup
      * requires code push
    * Backup not necessarily up to date
  * SOLR geospatial extensions not being utilized