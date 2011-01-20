from google.appengine.ext import db

class EventsData (db.Model):
  date_added = db.DateTimeProperty(auto_now_add=True)
  afg_story_id = db.StringProperty()
  fb_event_id = db.StringProperty()
  fb_user_id = db.StringProperty()
  fb_network_id = db.StringProperty(default='')

