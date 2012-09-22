""" """
import os
import logging

from google.appengine.dist import use_library
use_library('django', '1.2')

current_path = os.path.dirname(__file__)

pages_path = current_path.replace('/settings', '/pages')
TEMPLATE_DIRS = (
  pages_path
)

logging.info('settings: ' + pages_path)
