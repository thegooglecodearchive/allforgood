# Copyright 2009 Google Inc. All Rights Reserved.
# fb.py Facebook application related functions.

import datetime
import time
import os

from google.appengine.ext import webapp
from google.appengine.ext import db
from facebookapp.fb_model import EventsData

from third_party import json

class Events(webapp.RequestHandler):

  """ Utility function used for pagination. """
  def _getPostQuerystring(self):
    req = self.request
    records_per_page = req.get('records')
    start_index = req.get('start')
    if (not records_per_page):
      records_per_page = 50
    else:
      records_per_page = int(records_per_page)
    if (not start_index):
      start_index = 0
    else:
      start_index = int(start_index)
    returnString = ' LIMIT '
    returnString += str(records_per_page + 1)
    returnString += ' OFFSET '
    returnString += str(start_index)
    return returnString
      
  """
  To create facebook event mapping.
  The required URL parameters are user_id, story_id, event_id and network_id.
  The user_id is facebook user id.
  The story_id is 'fp:id' attribute of the 'All for Good' feed.
  The event_id is an unique id returned while an event is created in facebook application.
  """

  def addEvent(self):
    status = 'failure'
    data = ''
    req = self.request
    fb_user_id = req.get('user_id')
    afg_story_id = req.get('story_id')
    fb_event_id = req.get('event_id')
    fb_network_id = req.get('network_id')
    if (fb_user_id and afg_story_id and fb_event_id):
      eventsData = EventsData()
      eventsData.fb_user_id = fb_user_id
      eventsData.afg_story_id = afg_story_id
      eventsData.fb_event_id = fb_event_id
      eventsData.fb_network_id = fb_network_id
      reference = eventsData.put()
      status = 'success'
    output = {
      'status': status,
      'action': 'addEvent',
      'data': data
      }
    self.response.out.write(json.write(output))


  """
  To get facebook event mapping list.
  The required URL parameter is user_id.
  The user_id could ne either one or multiple users separated by comma(,').
  """
  def getEvents(self):
    req = self.request
    user_id = req.get('user_id')
    if (user_id.find(',') != -1):
      multiple_user = True
      user_id = user_id.split(',')
      # To restrict the number of sub queries to 25.
      user_id[25:] = []
    else:
      multiple_user = False
    events = self._getEvents(user_id, multiple_user)
    output = {
      'status': 'success',
      'data': events['data'],
      'order': events['order'],
      'action': 'getEvents'
      }
    self.response.out.write(json.write(output))

  """ Supportive function for getEvents. """
  def _getEvents(self, user_id, multiple_user):
    if (multiple_user):
      query = "select * from EventsData WHERE fb_user_id IN :1 ORDER BY date_added DESC"
    else:
      query = "select * from EventsData WHERE fb_user_id = :1 ORDER BY date_added DESC"
    query += self._getPostQuerystring()
    results = db.GqlQuery(query, user_id)
    events = {}
    order = []
    for result in results:
      event = {
        'reference': str(result.key()),
        'date_added': str(result.date_added),
        'story_id': str(result.afg_story_id),
        'event_id': str(result.fb_event_id),
        'user_id': str(result.fb_user_id),
        'network_id': str(result.fb_network_id)
        }
      order.append(str(result.afg_story_id))
      events[str(result.afg_story_id)] = event;
    return {'data': events, 'order': order};

  """
  To get facebook event  mapping list.
  The required URL parameter is network_id.
  """

  def getNetworkEvents(self):
    req = self.request
    network_id = req.get('network_id')
    if (not network_id):
      network_id = ''
    if (network_id.find(',') != -1):
      multiple_network = True
      network_id = network_id.split(',')
    else:
      multiple_network = False
    events = self._getNetworkEvents(network_id, multiple_network)
    output = {
      'status': 'success',
      'data': events['data'],
      'order': events['order'],
      'action': 'getEvents'
      }
    self.response.out.write(json.write(output))

  """ Supportive function for getNetworkEvents. """
  def _getNetworkEvents(self, network_id, multiple_network):
    if (multiple_network):
      query = "select * from EventsData WHERE fb_network_id IN :1 ORDER BY date_added DESC"
    else:
      query = "select * from EventsData WHERE fb_network_id = :1 ORDER BY date_added DESC"
    query += self._getPostQuerystring()
    results = db.GqlQuery(query, network_id)
    events = {}
    order = []
    for result in results:
      event = {
        'reference': str(result.key()),
        'date_added': str(result.date_added),
        'story_id': str(result.afg_story_id),
        'event_id': str(result.fb_event_id),
        'user_id': str(result.fb_user_id),
        'network_id': str(result.fb_network_id)
        }
      order.append(str(result.afg_story_id))
      events[str(result.afg_story_id)] = event;
    return {'data': events, 'order': order};

  """ Request handlers. """
  def get(self):
    try:
      # To check whether request is from authorised source.
      if os.getenv('REMOTE_ADDR') != '140.211.167.213':
        self.error(400)
        return
      path = self.request.path;

      if path.startswith('/fb/addEvent'):
        self.addEvent()
      elif path.startswith('/fb/getEvents'):
        self.getEvents()
      elif path.startswith('/fb/getNetworkEvents'):
        self.getNetworkEvents()
    except:
      pass

  def post(self):
    self.get()


