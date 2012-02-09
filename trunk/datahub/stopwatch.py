#!/usr/bin/python
"""usage: stopwatch.py [start, sleep, stop] seconds

start -- returns timestamp for now + seconds

sleep -- sleeps for seconds

stop  -- outputs 1 if now > seconds, else 0
"""

import os
import sys
import time
import datetime

def main():

  cmd = param = None
  for arg in sys.argv[1:]:
    if cmd:
      try:
        param = int(arg)
      except:
        print sys.modules['__main__'].__doc__
        sys.exit(1)

    if not cmd and arg in ['start', 'stop', 'sleep']:
      cmd = arg

  if not cmd or not param:
    print sys.modules['__main__'].__doc__
  elif cmd == 'start':
    future = datetime.datetime.now() + datetime.timedelta(seconds=int(param))
    print int(time.mktime(future.timetuple()))
  elif cmd == 'sleep':
    time.sleep(param)
  elif cmd == 'stop':
    now = datetime.datetime.now()
    if time.mktime(now.timetuple()) > param:
      print '1'
    else:
      print '0'
      
if __name__ == "__main__":
  main()

