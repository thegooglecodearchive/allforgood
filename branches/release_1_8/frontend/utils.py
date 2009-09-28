# Copyright 2009 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Miscellaneous utility functions.
"""

import hmac
import logging
import os

from xml.dom import minidom


class Error(Exception):
  pass


class InvalidValue(Error):
  pass


def get_xml_dom_text(node):
  """Returns the text of the first node found with the given tagname.
  Returns None if no node found."""
  text = ''
  for child in node.childNodes:
    if child.nodeType == minidom.Node.TEXT_NODE:
      text += child.data
  return text


def get_xml_dom_text_ns(node, namespace, tagname):
  """Returns the text of the first node found with the given namespace/tagname.
  Returns None if no node found."""
  child_nodes = node.getElementsByTagNameNS(namespace, tagname)
  if child_nodes:
    return get_xml_dom_text(child_nodes[0])


def xml_elem_text(node, tagname, default=None):
  """Returns the text of the first node found with the given namespace/tagname.
  returns default if no node found."""
  child_nodes = node.getElementsByTagName(tagname)
  if child_nodes:
    return get_xml_dom_text(child_nodes[0])
  return default

# Cached hmac object.
hmac_master = None

def signature(value):
  """Returns a signature for a param so we can compare it later.

  Examples: Signature(url) is compared in the url redirector to prevent other
  sites from using it. Signtaure(user_cookie) is used to limit XSRF attacks.
  """
  if not value:
    return None
  # This is a super cheesy way of avoiding storing a secret key...
  # It'll reset every minor update, but that's OK for now.
  global hmac_master
  if not hmac_master:
    hmac_master = hmac.new(os.getenv('CURRENT_VERSION_ID'))

  hmac_object = hmac_master.copy()
  hmac_object.update(value)
  return hmac_object.hexdigest()


def get_last_arg(request, argname, default):
  """Returns the last urlparam in an HTTP request-- this allows the
  later args to override earlier ones, which is easier for developers
  (vs. earlier ones taking precedence)."""
  values = request.get(argname, allow_multiple=True)
  if values:
    return values[-1]
  return default


def get_verified_arg(pattern, request, argname, default=None, last=True):
  """Return the (last) requested argument, if it passes the pattern.

  Args:
    pattern: A re pattern, e.g. re.compile('[a-z]*$')
    request: webob request
    argname: argument to look for
    default: value to return if not found
    last: use the last argument or first argument?

  Returns:
    Value in the get param, if prsent and valid. default if not present.

  Raises:
    InvalidValue exception if present and not valid.
  """
  values = request.get(argname, allow_multiple=True)
  if not values:
    return default

  if last:
    value = values[-1]
  else:
    value = value[0]

  if not pattern.match(value):
    raise InvalidValue

  return value
