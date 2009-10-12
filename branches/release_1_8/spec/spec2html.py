#!/usr/bin/python
#
# didn't use generateDS because it required a slew of packages to be installed,
# like pulling on a sweater.

"""horrible regexp-based converter from XSD to human-readable HTML."""

# disable line too long-- irrelevant here
# pylint: disable-msg=C0301

# usage: python spec2html.py < spec0.1.xsd > spec0.1.html

import sys
import re

def main():
  """wrap the code in scope."""
  outstr = sys.stdin.read()
  version = (re.findall(r'<xs:schema version="(.+?)"', outstr))[0]
  outstr = re.sub(r'(\r?\n|\r)', r'', outstr)
  outstr = re.sub(r'<[?]xml.+?>', r'', outstr)
  outstr = re.sub(r'</?xs:schema.*?>', r'', outstr)
  outstr = re.sub(r'<code>(.+?)</code>', r'<a href="#\1"><code>\1</code></a>', outstr)
  outstr = re.sub(r'<pcode>(.+?)</pcode>', r'<code>\1</code>', outstr)
  outstr = re.sub(r'<(/?(code|p|a|br|b).*?)>', r'&&\1@@', outstr)
  outstr = re.sub(r'<', r'', outstr)
  outstr = re.sub(r'/?>', r'', outstr)
  
  #blockquoting
  outstr = re.sub(r'/xs:(all|sequence)', r'</blockquote>', outstr)
  #Change element to selement for distinguishing multiple entries later on
  outstr = re.sub(r'xs:sequence(.+?)xs:element', r'xs:sequence\1xs:selement', outstr)
  #blockquoting
  outstr = re.sub(r'xs:(all|sequence)', r'<blockquote>', outstr)
  
  #Named types
  outstr = re.sub(r'xs:(simple|complex)Type name="(.+?)"(.+?)/xs:(simple|complex)Type',
                  r'<div class="namedType"><div class="entryName"><a name="\2">\2 (\1 type)</a></div>\3</div>', outstr)
  
  #Extension
  outstr = re.sub(r'xs:extension\s+?base="(xs:)?(.+?)"(.+?)/xs:extension', r'<div class="info">derived from: \2</div>\3', outstr)
  
  #restriction
  outstr = re.sub(r'xs:restriction\s+?base="(xs:)?(.+?)"(.+?)/xs:restriction', r'<div class="info">derived from: \2</div>\3', outstr)
  
  #attribute entries
  outstr = re.sub(r'/xs:attribute', r'</blockquote></div>\n', outstr)
  outstr = re.sub(r'\s*xs:attribute name="(.+?)"', r'<div class="entry"><blockquote><div class="entryName"><a name="\1">\1 (attribute)</a></div>\n', outstr)
  
  #element entries
  outstr = re.sub(r'/xs:element', r'</div>\n', outstr)
  outstr = re.sub(r'\s*xs:selement name="(.+?)"(.+?)', r'<div class="entry repeated"><div class="entryName"><a name="\1">\1 (repeated element)</a></div>\n', outstr)
  outstr = re.sub(r'\s*xs:element name="(.+?)"(.+?)', r'<div class="entry"><div class="entryName"><a name="\1">\1 (element)</a></div>\n', outstr)
  
  #documentation
  outstr = re.sub(r'xs:annotation\s+xs:documentation\s+!\[CDATA\[\s*(.+?)\s*\]\]\s+/xs:documentation\s+/xs:annotation', r'<div class="doc-text">\1</div>', outstr)
  
  #Little stuff in entries
  outstr = re.sub(r'use="(.+?)"', r'<span class="info">use is \1</span><br/>', outstr)
  outstr = re.sub(r'default=""', r'<span class="info">default value: <code>(empty string)</code></span><br/>', outstr)
  outstr = re.sub(r'default="(.+?)"', r'<span class="info">default value: <code>\1</code></span><br/>', outstr)
  outstr = re.sub(r'fixed="(.+?)"', r'<span class="info">fixed value: <code>\1</code></span><br/>', outstr)
  outstr = re.sub(r'xs:enumeration value="(.+?)"', r'<span class="info">allowed value: <code>\1</code></span><br/>', outstr)
  outstr = re.sub(r'xs:pattern value="(.+?)"', r'<span class="info">must match (regular expression): <code>\1</code></span><br/>', outstr)
  outstr = re.sub(r'type="(xs:)?(.+?)"', r'<span class="info">datatype: \2</span><br/>', outstr)
  outstr = re.sub(r'minOccurs="0"', r'<span class="info">required: optional.</span><br/>', outstr)
  outstr = re.sub(r'minOccurs="([0-9]+)"', r'<span class="info">required: at least \1 times</span><br/>', outstr)
  outstr = re.sub(r'maxOccurs="1"', r'<span class="info">Multiple not allowed</span><br/>', outstr)
  outstr = re.sub(r'maxOccurs="unbounded"', r'\n', outstr)
  
  #putting in links
  outstr = re.sub(r'(datatype|derived from): (locationType|dateTimeDurationType|yesNoEnum|sexRestrictedEnum|dateTimeOlsonDefaultPacific|timeOlson|dateTimeNoTZ|timeNoTZ)', r'\1: <a href="#\2"><code>\2</code></a>\n', outstr)
  outstr = re.sub(r'(datatype|derived from): (string)', r'\1: <a href="http://www.w3schools.com/Schema/schema_dtypes_string.asp"><code>\2</code></a>\n', outstr)
  outstr = re.sub(r'(datatype|derived from): (dateTime|date|time|duration)', r'\1: <a href="http://www.w3schools.com/Schema/schema_dtypes_date.asp"><code>\2</code></a>\n', outstr)
  outstr = re.sub(r'(datatype|derived from): (integer|decimal)', r'\1: <a href="http://www.w3schools.com/Schema/schema_dtypes_numeric.asp"><code>\2</code></a>\n', outstr)
  
  #Drop stuff we don't care about
  outstr = re.sub(r'/?xs:(simpleContent|complexType)', r'', outstr)
  
  #clean-up
  outstr = re.sub(r'&&', r'<', outstr)
  outstr = re.sub(r'@@', r'>', outstr)
  outstr = re.sub(r'\s*<br/>', r'<br/>\n', outstr)
  
  print "<html>"
  print "<head>"
  print "<title>Footprint XML Specification Version", version, "</title>"
  #print '<LINK REL="StyleSheet" HREF="spec.css" TYPE="text/css"/>'
  print "<style>"
  cssfh = open('spec.css')
  print cssfh.read()
  print "</style>"
  print "</head>"
  print "<body>"
  print '<div class="titleText">Footprint XML Specification Version', version, '</div><br>'
  print outstr
  print "</body></html>"

main()
