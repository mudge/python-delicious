import httplib2
import datetime
from urllib.parse import urlencode
try:
  from lxml import etree
except ImportError:
  import xml.etree.ElementTree as etree

class Account:
  '''user account for Delicious providing access to bookmarks and tags'''
  
  def __init__(self, username, password):
    self.username = username
    self.password = password
    self.h = httplib2.Http('.cache')
    self.h.add_credentials(username, password, 'api.del.icio.us')
  
  def last_update(self):
    '''the last update time for the user, as well as the number of new items in the user's inbox since it was last visited'''
    response, content = self.h.request('https://api.del.icio.us/v1/posts/update')
    if response.status == 200:
      
      # Make a copy of the attributes.
      attributes = dict(etree.fromstring(content).attrib)
      self.parse_time(attributes)
      return attributes
      
  def recent_bookmarks(self, count=None, tag=None):
    parameters = {}
    if count:
      parameters['count'] = count
    if tag:
      parameters['tag'] = tag
    response, content = self.h.request('https://api.del.icio.us/v1/posts/recent?' + urlencode(parameters))
    if response.status == 200:
      bookmarks = [self.parse_time(dict(post.attrib)) for post in etree.fromstring(content).findall('post')]
      return bookmarks
  
  def parse_time(self, timed_item):
    timed_item['time'] = datetime.datetime.strptime(timed_item['time'], '%Y-%m-%dT%H:%M:%SZ')
    return timed_item