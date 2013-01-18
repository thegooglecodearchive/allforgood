import os
import re

DIRECT_FIELDS = [                                                                                    
  'OpportunityID', 
  'volunteersNeeded',                                                                                    
  'sexRestrictedTo', 
  'contactName',                                                            
  'contactPhone', 
  'contactEmail', 
  'providerURL', 
  'language', 
  'lastUpdated', 
  'expires',                   

  # HON 2012/05/24
  # http://www.avviato.net/afg/spec0.1.r1254_Sugested05242012.html
  'scheduleType',
  'activityType', # activityTypes
  'invitationCode',
  'managedBy',
  'registerType',
  'affiliateOrganizationID',
  'isDisaster',
  'opportunityType',
  'frequency',
  'frequencyURL',
  'minimumAge',                                                                                          

  'eventId',
  'eventName',
  'occurrenceId', 
  'occurrenceDuration',

  'categories',                   

  'appropriateFor', #appropriatFors
  'audienceTag', #audienceTags
  'population', # populations
  'dayWeek', # availabilityDays
  'categoryTag', #categoryTags
  'skill', #skills

  'sponsoringOrganizationID', 
  'rsvpCount',
  #'additionalInfoRequired', #Custom questions required for the VO not declared because requires a additional processing so it is not a direct field
]                                                                                                        

def main():

  fh = file('handsonnetworkconnect.xml', 'r')
  xml = fh.read()
  fh.close()

  for field in DIRECT_FIELDS:
    print field,
    expr = re.compile(field)
    results = expr.search(xml)
    if results:
      print 'ok'
    else:
      expr = re.compile(field, re.IGNORECASE)
      results = expr.search(xml)
      if results:
        print 'case', results.group(0)
      else:
        print 'not in feed'


if __name__ == "__main__":
  main()
