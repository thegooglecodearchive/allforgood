# pagecount.py
#
# memcache-based counter with occasional db writeback.
# This is suitable for realtime pageviews counts, YMMV for other uses.
#

from google.appengine.api import memcache
from google.appengine.ext import db
import logging
import random

# this is a key used for testing and calls made with it
# are seperated from the production stats
TEST_API_KEY = 'testkey'

VIEWS_PREFIX = "v:"
CLICKS_PREFIX = "c:"

# increase as needed
WRITEBACK_FREQ_PCT = 1.0
WRITEBACK_VAL = WRITEBACK_FREQ_PCT / 100.0 * 1000000.0

pc_writebacks = 0
pc_loads = 0

class PageCountShard(db.Model):
  count = db.IntegerProperty(default=0)

def KeyName(pagename):
  return 'pc:' + pagename

def Writeback(pagename, value):
  global pc_writebacks
  pc_writebacks = pc_writebacks + 1
  logging.debug("pagecount.Writeback(pagename='%s', value=%d" % (pagename, +value))
  record = PageCountShard(key_name=KeyName(pagename), count=value)
  try:
    record.put()
  except:
    logging.warning("pagecount.Writeback(pagename='%s', value=%d" % (pagename, +value))

def LoadPageCount(pagename):
  global pc_loads
  pc_loads = pc_loads + 1
  logging.debug("pagecount.LoadPageCount(pagename='"+pagename+"')")
  try:
    record = PageCountShard.get_by_key_name(KeyName(pagename))
  except:
    record = None

  if record != None:
    return record.count
  db.run_in_transaction(Writeback, pagename, 0)
  return 0

# initializes memcache if missing
def GetPageCount(pagename):
  logging.debug("pagecount.GetPageCount(pagename='"+pagename+"')")
  memcache_id = KeyName(pagename)
  val = memcache.get(memcache_id)
  if (val != None):
    return val
  val = LoadPageCount(pagename)
  memcache_id = KeyName(pagename)
  memcache.set(memcache_id, val)
  return val

def IncrPageCount(pagename, delta):
  """ increment page count """
  logging.debug("pagecount.IncrPageCount(pagename='"+pagename+"')")
  memcache_id = KeyName(pagename)
  if memcache.get(memcache_id) == None:
    # initializes memcache if missing
    return GetPageCount(pagename)
  newval = memcache.incr(memcache_id, delta)
  #TODO: rnd seems unused?
  #rnd = random.random() * 1000000.0
  
  if (random.random() * 1000000.0 <= WRITEBACK_FREQ_PCT / 100.0 * 1000000.0):
    logging.debug("pagecount.IncrPageCount: writeback: writebacks="+
                  str(pc_writebacks)+" newval="+str(newval))
    db.run_in_transaction(Writeback, pagename, newval)
  return newval

def GetStats():
  global pc_writebacks, pc_loads
  stats = memcache.get_stats()
  stats['pc_writebacks'] = pc_writebacks
  stats['pc_loads'] = pc_loads
  return stats

