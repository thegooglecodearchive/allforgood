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
  """Converts an integer value to a letter (assumption: 0 <= value < 26)."""
  if 0 <= value < 26:
    return chr(ord('A') + value)
  else:
    return ''

def bold_query(value, query):
  """Bolds all instances of query in value"""
  if query:
    return value.replace(query, "<strong>%s</strong>" % query)
  else:
    return value

# Prevents pylint from triggering on the 'register' name. Django expects this
# module to have a 'register' variable.
# pylint: disable-msg=C0103
register = webapp.template.create_template_register()
register.filter('truncate_chars', truncate_chars)
register.filter('as_letter', as_letter)
register.filter('bold_query', bold_query)
