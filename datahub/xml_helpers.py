#!/usr/bin/python
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
dumping ground for functions common across all parsers.
"""

from xml.dom import minidom
from datetime import datetime
import xml.sax.saxutils
import xml.parsers.expat
import re
import sys
import time


import utf8

# asah: I give up, allowing UTF-8 is just too hard without incurring
# crazy performance penalties
SIMPLE_CHARS = ''.join(map(chr, range(32, 127)))
SIMPLE_CHARS_CLASS = '[^\\n%s]' % re.escape(SIMPLE_CHARS)
SIMPLE_CHARS_RE = re.compile(SIMPLE_CHARS_CLASS)
DEFAULT_TRACE_LOG = "trace.log"

PROGRESS_START_TS = datetime.now()

def clean_string(instr):
  """return a string that's safe wrt. utf-8 encoding."""
  #print "SIMPLE_CHARS_CLASS=",SIMPLE_CHARS_CLASS
  instr = instr.decode('ascii', 'replace')
  return SIMPLE_CHARS_RE.sub('', instr).encode('UTF-8')

def node_data(entity):
  """get the data buried in the given node and escape it."""
  if (entity.firstChild == None):
    return ""
  if (entity.firstChild.data == None):
    return ""
  outstr = entity.firstChild.data
  outstr = xml.sax.saxutils.escape(outstr).encode('UTF-8')
  outstr = re.sub(r'\n', r'\\n', outstr)
  return outstr
  
def get_children_by_tagname(elem, name):
  """get all the children with a given name."""
  temp = []
  for child in elem.childNodes:
    if child.nodeType == child.ELEMENT_NODE and child.nodeName == name:
      temp.append(child)
  return temp


def processing_trace(src, msg, trace_log = DEFAULT_TRACE_LOG):
  try:
    fh = open(trace_log, 'a')
    log_entry = [str(datetime.now()), src, msg]
    fh.write("\t".join(log_entry) + "\n")
    fh.close()
  except:
    pass
  

def print_progress(msg, filename="", progress=True):
  """print progress indicator."""
  if progress:
    print str(datetime.now())+":"+filename, msg

def print_status(msg, filename="", progress=True):
  """print status indicator, for stats collection."""
  print_progress(msg, "STATUS:"+filename, progress)

def print_rps_progress(noun, progress, recno, maxrecs):
  """print a progress indicator."""
  return 

  maxrecs_str = ""
  if maxrecs > 0:
    maxrecs_str = " of " + str(maxrecs)
  if progress and recno > 0 and recno % 250 == 0:
    now = datetime.now()
    secs_since_start = now - PROGRESS_START_TS
    secs_elapsed = 3600*24.0*secs_since_start.days + \
        1.0*secs_since_start.seconds + \
        secs_since_start.microseconds / 1000000.0
    rps = recno / secs_elapsed
    print str(now)+": ", recno, noun, "processed" + maxrecs_str +\
        " ("+str(int(rps))+" recs/sec)"

def get_tag_val(entity, tag):
  """walk the DOM of entity looking for the first child named (tag)."""
  #print "----------------------------------------"
  if not entity:
    return ""
  try:
    nodes = entity.getElementsByTagName(tag)
  except:
    return ""
  
  if (nodes.length == 0):
    return ""
  
  if (nodes[0] == None):
    return ""

  if (nodes[0].firstChild == None):
    return ""

  try:
    if (nodes[0].firstChild.data == None):
      return ""
  except:
    return ""

  outstr = ""
  for node in nodes[0].childNodes:
    if node.nodeType == node.TEXT_NODE:
      outstr += xml.sax.saxutils.unescape(node.data.strip()).encode('UTF-8')
    elif node.nodeType == node.CDATA_SECTION_NODE:
      outstr += node.data.strip().encode('UTF-8')
  #outstr = re.sub(r'\n', r'\\n', outstr)
  outstr = re.sub(r'\n', ' ', outstr)
  outstr = "".join(i for i in outstr if ord(i)<128 and ord(i)>31)
  return outstr

def get_tag_attr(entity, tag, attribute):
  """Finds the first element named (tag) and returns the named
  attribute."""
  if not entity:
    return ""
  nodes = entity.getElementsByTagName(tag)
  if (nodes.length == 0):
    return ""
  if (nodes[0] == None):
    return ""
  outstr = nodes[0].getAttribute(attribute)
  outstr = xml.sax.saxutils.escape(outstr).encode('UTF-8')
  outstr = re.sub(r'\n', ' ', outstr)
  outstr = "".join(i for i in outstr if ord(i)<128 and ord(i)>31)
  return outstr

def set_default_value(parent, entity, tagname, default_value):
  """add the element if not already present in the DOM tree."""
  if not parent or not entity:
    return 
  try:
    nodes = entity.getElementsByTagName(tagname)
  except:
    return

  if len(nodes) == 0:
    newnode = parent.createElement(tagname)
    newnode.appendChild(parent.createTextNode(str(default_value)))
    return newnode
  return nodes[0]

def set_default_attr(doc, entity, attrname, default_value):
  """create and set the attribute if not already set."""
  if not entity:
    return
  if entity.getAttributeNode(attrname) == None:
    entity.setAttribute(attrname, default_value)


def validate_xml(xmldoc, known_elnames):
  """a simple XML validator, given known tagnames."""
  if xmldoc and xmldoc.childNodes:
    for node in xmldoc.childNodes:
      if (node.nodeType == node.ELEMENT_NODE and
          node.tagName not in known_elnames):
        #print "unknown tagName '"+node.tagName+"'"
        pass
        # TODO: spellchecking...
      validate_xml(node, known_elnames)


def parse_or_die(instr):
  xmldoc = None

  try:
    xmldoc = minidom.parseString(instr)
  except xml.parsers.expat.ExpatError, err:
    print datetime.now(), "XML parsing error on line ", err.lineno,
    print ":", xml.parsers.expat.ErrorString(err.code),
    print " (column ", err.offset, ")"
    lines = instr.split("\n")
    for i in range(err.lineno - 3, err.lineno + 3):
      if i >= 0 and i < len(lines):
        print "%6d %s" % (i+1, lines[i])

  if not xmldoc:
    print "trying CDATA detailURL..."
    instr = instr.replace('<detailURL>', '<detailURL><![CDATA[').replace('</detailURL>', ']]></detailURL>')
    try:
      xmldoc = minidom.parseString(instr)
    except:
      pass

  if not xmldoc:
    print "trying CDATA description..."
    instr = instr.replace('<description>', '<description><![CDATA[').replace('</description>', ']]></description>')
    try:
      xmldoc = minidom.parseString(instr)
    except:
      pass

  if not xmldoc:
    print "trying CDATA title..."
    instr = instr.replace('<title>', '<title><![CDATA[').replace('</title>', ']]></title>')
    try:
      xmldoc = minidom.parseString(instr)
    except:
      pass

  if not xmldoc:
    print "trying CDATA city..."
    instr = instr.replace('<city>', '<city><![CDATA[').replace('</city>', ']]></city>')
    try:
      xmldoc = minidom.parseString(instr)
    except:
      pass

  if not xmldoc:
    print "trying CDATA region..."
    instr = instr.replace('<region>', '<region><![CDATA[').replace('</region>', ']]></region>')
    try:
      xmldoc = minidom.parseString(instr)
    except:
      pass

  if not xmldoc:
    print "trying anyway ..."
    from BeautifulSoup import BeautifulStoneSoup
    try:
      xmldoc = BeautifulStoneSoup(instr)
    except:
      pass

  if not xmldoc:
    print "xml_helpers.parse_or_die: this feed is unparseable -- contact provider"
    sys.exit(0)

  return xmldoc


def simple_parser(instr, known_elnames_list, progress):
  """a simple wrapper for parsing XML which attempts to handle errors."""

  xmldoc = None
  if progress:
    print datetime.now(), "xml_helpers.simple_parser: parsing XML"

  xmldoc = parse_or_die(instr)

  if progress:
    print datetime.now(), "xml_helpers.simple_parser: validating XML..."

  if known_elnames_list:
    known_elnames_dict = {}
    for item in known_elnames_list:
      known_elnames_dict[item] = True
    validate_xml(xmldoc, known_elnames_dict)

  if progress:
    print datetime.now(), "xml_helpers.simple_parser: done parsing"

  return xmldoc


def prettyxml(doc, strip_header = False):
  """return pretty-printed XML for doc."""
  if doc and doc.toxml:
    outstr = doc.toxml("UTF-8")
  else:
    outstr = ''
  if strip_header:
    outstr = re.sub(r'<\?xml version="1.0" encoding="UTF-8"\?>', r'', outstr)
  outstr = re.sub(r'><', r'>\n<', outstr)
  # toprettyxml wasn't that pretty...
  return outstr

def output_val(name, val):
  """return <name>val</name>."""
  return "<" + name + ">" + str(val) + "</" + name + ">"
def output_node(name, node, nodename):
  """return <name>get_tag_val(node)</name>."""
  return output_val(name, xml.sax.saxutils.escape(get_tag_val(node, nodename)))
def output_plural(name, val):
  """return <names><name>val</name></names>."""
  return "<" + name + "s>" + output_val(name, val) + "</" + name + "s>"
def output_plural_node(name, node, nodename):
  """return <names><name>get_tag_val(node)</name></names>."""
  return "<" + name + "s>" + output_node(name, node, nodename) + \
      "</" + name + "s>"
  
def current_ts(delta_secs=0):
  """Return a formatted datetime string for the current time, e.g.
  2008-12-30T14:30:10.5"""
  return time.strftime("%Y-%m-%dT%H:%M:%S",
                       time.gmtime(time.mktime(time.gmtime()) + delta_secs))

def current_time(delta_secs=0):
  """Return a formatted time string for the current time, e.g. 14:30:10.5"""
  return time.strftime("%H:%M:%S",
                       time.gmtime(time.mktime(time.gmtime()) + delta_secs))

def current_date(delta_secs=0):
  """Return a formatted date string for the current time, e.g. 2008-12-30"""
  return time.strftime("%Y-%m-%d",
                       time.gmtime(time.mktime(time.gmtime()) + delta_secs))

