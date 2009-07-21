''' taggers.py contains Tagger classes used in tagging.py to tag listings '''
class Tagger(object):
  ''' Tagger is the base class for all Taggers.  Each Tagger instance
  tags multiple rows (from TSVs). '''
  def __init__(self, tag_name, tag_col):
    ''' Create instance variables '''
    self.tag_name = tag_name # The tag this Tagger will apply - set in the subclass
    self.score_threshold = 1.0 # Score (between 0 and 1) necessary to apply tag
    self.tag_col = tag_col # Column to add tags to

    # Each Tagger has one or more tagging functions, defined in subclasses.
    # Tagging functions take a row as an input and return a score
    # between 0.0 and 1.0.  The scores are then averaged and compared
    # to the threshold.  This is a list because a subclass of Tagger can inherit
    # from multiple types of Taggers.
    self.tagging_functions = []

  
  def do_tagging(self, row):
    ''' takes a row to be tagged, runs tagging functions'''
    scores = []
    for func in self.tagging_functions:
      scores.append(func(row))
    
    # get the average score from the tagging functions
    score = reduce(lambda x, y: x+y, scores)/len(scores)
    
    # add tag if the score, after all tagging functions, exceeds the threshold
    if score > self.score_threshold:
      row[self.tag_col] += self.tag_name + ', '
    return row

class KeywordTagger(Tagger):
  ''' KeywordTagger is a base class for all Taggers that apply basic tagging 
  rules based on if a keyword appears in the description of a listing. '''
  def __init__(self, tag_name, keywords_dict, examine_cols, tag_col):
    ''' Create relevant variables for the KeywordTagger. '''
    Tagger.__init__(self, tag_name, tag_col)
    self.examine_cols = examine_cols # Columns to check for the keyword
    
    # Keywords holds the keywords that trigger this tag, along with the amount
    # increment the score by (between 0.0 and 1.0) for each keyword.
    self.keywords = keywords_dict
    
    self.score_threshold = 0.0 # right now, we'll tag if any keywords match
    self.tagging_functions.append(self.tag_by_keywords)
  
  def tag_by_keywords(self, row):
    ''' Takes the keywords defined in subclasses and checks them against
    the description, returning the average score. '''
    score = 0.0
    for keyword in self.keywords:
      keyword_count = 0
      for col in self.examine_cols:
        keyword_count += row[col].lower().count(keyword.lower())
      if keyword_count > 0:
        score += self.keywords[keyword]
    score /= len(self.keywords)
    return score

class SimpleKeywordTagger(KeywordTagger):
  ''' Creates a KeywordTagger from a whitespace separated list of keywords
  rather than a dict, with each keyword having a score of 1.0. '''
  def __init__(self, tag_name, keywords_list, examine_cols, tag_col):
    '''Expand the whitespace separated list and call the KeywordTagger init '''
    keywords_dict = dict(zip(keywords_list.split(),[1.0 for i in range(0,len(keywords_list))]))
    KeywordTagger.__init__(self, tag_name, keywords_dict, examine_cols, tag_col)

''' Right now, EducationTagger is implemented just as an instance of
KeywordTagger, but in the future it may want to inherit from multiple
Tagger types.  This code is how it would be implemented as a subclass.
class EducationTagger(KeywordTagger):
  def __init__(self, examine_cols, tag_col):
    KeywordTagger.__init__(self, 'Education', {'education':1.0, 'school':1.0, \
                      'teacher':1.0, 'classroom':1.0, 'leaning':1.0}, \
                      examine_cols, tag_col)
'''