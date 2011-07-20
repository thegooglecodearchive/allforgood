#!/usr/bin/python

import sys
import re

lineno = 0
for line in sys.stdin:
  line = re.sub(r'[\r\n]+$', "", line)
  lineno += 1
  fields = line.split("\t")
  outstr = str(lineno) + "\t"
  outstr += fields[7] + "\t"
  outstr += "url:"+fields[30] + "\n"

  outstr += fields[13] + "\n"

  outstr += fields[45] + "\t"
  outstr += "(" + fields[52] + "," + fields[53] + ", " + fields[54] + ")"
  print outstr
