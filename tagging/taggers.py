''' taggers.py contains Tagger classes used in tagging.py to tag listings '''
class Tagger(object):
  ''' Tagger is the base class for all Taggers.  Each Tagger instance
  tags multiple rows (from TSVs). '''
  def __init__(self):
    ''' Create instance variables '''
    self.tag = '' # The tag this Tagger will apply - set in the subclass
    self.score_threshold = 1.0 # Score (between 0 and 1) necessary to apply tag
    self.rows = [] # Holds the list of rows that have gone through the tagger

    # Each Tagger has one or more tagging functions, defined in subclasses.
    # Tagging functions take a row as an input and return a score
    # between 0.0 and 1.0.  The scores are then averaged and compared
    # to the threshold.  This is a list because a subclass of Tagger can inherit
    # from multiple types of Taggers.
    self.tagging_functions = []

    # These hold the column IDs for applicable fields in the imported TSVs
    # TODO: Determine the columns each run from the file
    self.row_title = 7
    self.row_description = 8
    self.row_tags = 42
  
  def do_tagging(self, row):
    ''' takes a row to be tagged, runs tagging functions'''
    scores = []
    for func in self.tagging_functions:
      scores.append(func(row))
    
    # get the average score from the tagging functions
    score = reduce(lambda x, y: x+y, scores)/len(scores)
    
    # add tag if the score, after all tagging functions, exceeds the threshold
    if score > self.score_threshold:
      row[self.row_tags] += self.tag + ' '
      #print "Tagging", self.title(row), self.tag, "with score", score
    self.rows.append(row)
    return row
  
  def title(self, row):
    ''' simplifies returning the title field in a row '''
    return row[self.row_title]
  
  def description(self, row):
    ''' simplifies returning the description field in a row'''
    return row[self.row_description]

class KeywordTagger(Tagger):
  ''' KeywordTagger is a base class for all Taggers that apply basic tagging 
  rules based on if a keyword appears in the description of a listing. '''
  def __init__(self):
    ''' Create relevant variables for the KeywordTagger. '''
    Tagger.__init__(self)
    
    # Keywords is defined in subclasses and holds the keywords that
    # trigger this tag, along with the amount to increment the score by
    # (between 0.0 and 1.0) for each keyword.
    self.keywords = {}
    
    self.score_threshold = 0.0 # right now, we'll tag if any keywords match
    self.tagging_functions.append(self.tag_by_keywords)
  
  def tag_by_keywords(self, row):
    ''' Takes the keywords defined in subclasses and checks them against
    the description, returning the average score. '''
    score = 0.0
    for keyword in self.keywords:
      if self.description(row).count(keyword) > 0:
        score += self.keywords[keyword]
    score /= len(self.keywords)
    return score

  
class NatureTagger(KeywordTagger):
  ''' Tagger for tag 'nature' using keywords '''
  def __init__(self):
    KeywordTagger.__init__(self)
    self.tag = 'Nature'
    self.keywords = {'nature':1.0, 'wetlands':1.0, 'park':1.0, \
                     'forest':1.0, 'trees':1.0}
  
class EducationTagger(KeywordTagger):
  ''' Tagger for tag 'education' using keywords '''
  def __init__(self):
    KeywordTagger.__init__(self)
    self.tag = 'Education'
    self.keywords = {'education':1.0, 'school':1.0, 'teacher':1.0, \
                     'classroom':1.0}