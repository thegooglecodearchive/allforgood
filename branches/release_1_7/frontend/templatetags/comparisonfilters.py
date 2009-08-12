# http://code.djangoproject.com/wiki/BasicComparisonFilters
# with modifications to work in AppEngine:
#   http://4.flowsnake.org/archives/459

# from django.template import Library
from google.appengine.ext import webapp

def gt(value, arg):
    """Returns a boolean of whether the value is greater than the
    argument"""
    return value > int(arg)

def lt(value, arg):
    """Returns a boolean of whether the value is less than the argument"""
    return value < int(arg)

def gte(value, arg):
    """Returns a boolean of whether the value is greater than or equal to
    the argument"""
    return value >= int(arg)

def lte(value, arg):
    """Returns a boolean of whether the value is less than or equal to
    the argument"""
    return value <= int(arg)

def length_gt(value, arg):
    """Returns a boolean of whether the value's length is greater than
    the argument"""
    return len(value) > int(arg)

def length_lt(value, arg):
    """Returns a boolean of whether the value's length is less than the
    argument"""
    return len(value) < int(arg)

def length_gte(value, arg):
    """Returns a boolean of whether the value's length is greater than or
    equal to the argument"""
    return len(value) >= int(arg)

def length_lte(value, arg):
    """Returns a boolean of whether the value's length is less than or
    equal to the argument"""
    return len(value) <= int(arg)

# This was not in the original library.
def isin(a, b):
  """Checks if a is contained in b."""
  return a in b

# register = Library()
register = webapp.template.create_template_register()
register.filter('gt', gt)
register.filter('lt', lt)
register.filter('gte', gte)
register.filter('lte', lte)
register.filter('length_gt', length_gt)
register.filter('length_lt', length_lt)
register.filter('length_gte', length_gte)
register.filter('length_lte', length_lte)
register.filter('isin', isin)