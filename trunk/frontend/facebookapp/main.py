# Standard libraries
import wsgiref.handlers

# AppEngine imports
from google.appengine.ext import webapp

from facebookapi import fb

# Map URLs to request handler class
application = webapp.WSGIApplication([
                                      ('/fb/addEvent', fb.Events),
                                      ('/fb/removeEvent', fb.Events),
                                      ('/fb/getEvents', fb.Events),
                                      ('/fb/getNetworkEvents', fb.Events),
                                      ],
                                     debug=True)

# Fire it up!
wsgiref.handlers.CGIHandler().run(application)
