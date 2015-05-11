# Search Architecture #

## Data Flow ##
  1. Create url for for Get against the SOLR instance
  1. Execute Get
  1. Parse response and create searchResultSet
  1. Score the opportunities for return order
  1. Remove duplicate opportunities