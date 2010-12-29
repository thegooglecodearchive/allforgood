# http://w.holeso.me/2008/08/a-simple-django-truncate-filter/
# with modifications to work in AppEngine:
#   http://4.flowsnake.org/archives/459

"""
Custom filters and tags for strings.
"""

from google.appengine.ext import webapp

def truncate_chars(value, max_length):
  """Truncate filter."""
  if len(value) > max_length:
    truncated_value = value[:max_length]
    ellipsis = ' ...'
    if value[max_length] != ' ':
      # TODO: Make sure that only whitespace in the data records
      #     is ascii spaces.
      right_index = truncated_value.rfind(' ')
      MAX_CHARS_TO_CLIP = 40 # pylint: disable-msg=C0103
      if right_index < max_length - MAX_CHARS_TO_CLIP:
        right_index = max_length - MAX_CHARS_TO_CLIP
        ellipsis = '...'  # No separating space
      truncated_value = truncated_value[:right_index]
    return  truncated_value + ellipsis
  return value


def as_letter(value):
  """ Converts an integer value to a letter (assumption: 0 <= value < 26). """
  if 0 <= value < 26:
    return chr(ord('A') + value)
  else:
    return ''

def bold_query(value, query):
  """ Bolds all instances of query in value """
  if query:
    for term in split_query(query):
      value = bold_term(value, term)
  return value

def bold_term(value, term):
  """ Returns value with all instances of term bolded, case-insensitive """
  nocase_value = value.lower()
  nocase_term = term.lower()
  start_loc = nocase_value.find(nocase_term)
  if start_loc == -1:
    return value
  else:
    end_loc = start_loc + len(nocase_term)
    return '%s<strong>%s</strong>%s' % (value[0:start_loc], 
            value[start_loc:end_loc], bold_term(value[end_loc:], term))

def split_query(query):
  """ Split a search query into a list of terms to bold """
  terms = []

  # Add terms in quotes
  while query.count('"') >= 2:
    first = query.find('"')
    second = query.find('"', first+1)
    # Check if the term should be excluded
    start = first-1
    while query[start].isspace():
      start -= 1
    if query[start] != '-':
      terms.append(query[first+1:second])
    query = '%s %s' % (query[0:start+1], query[second+1:len(query)])

  # Remove ANDs and ORs - we only want a list of terms to bold,
  # so ANDs and ORs don't matter
  query = query.replace(" AND "," ")
  query = query.replace(" OR "," ")

  # Remove items excluded from the search
  while query.count('-') >= 1:
    loc = query.find('-')
    remainder = query[loc+1:].split(None, 1)    # find the text after the -
    if len(remainder) > 1:    # remove the excluded term from the query
      query = '%s %s' % (query[0:loc], remainder[1])
    else:    # add the - as a term if nothing appears after it
      terms.append('-')
      query = query[0:loc]

  terms += query.split()    # Add other terms, separated by spaces
  return list(set(terms))    # Return only the unique terms

def add_commas(value):
  """adds commas to numbers, from http://www.djangosnippets.org/snippets/1155/"""
  import re
  __test__ = {}
  re_digits_nondigits = re.compile(r'\d+|\D+')
  parts = re_digits_nondigits.findall('%i' % (value,))
  for i in xrange(len(parts)):
    s = parts[i]
    if s.isdigit():
      r = []
      for j, c in enumerate(reversed(s)):
        if j and (not (j % 3)):
          r.insert(0, ',')
        r.insert(0, c)
      parts[i] = ''.join(r)
      break
  return ''.join(parts)

def getkey(value, arg):
  return value[arg]
  
# Prevents pylint from triggering on the 'register' name. Django expects this
# module to have a 'register' variable.
# pylint: disable-msg=C0103
register = webapp.template.create_template_register()
register.filter('truncate_chars', truncate_chars)
register.filter('as_letter', as_letter)
register.filter('bold_query', bold_query)
register.filter('add_commas', add_commas)
register.filter('getkey', getkey)
