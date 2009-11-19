import httplib2
import datetime
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
      attributes['time'] = datetime.datetime.strptime(attributes['time'], '%Y-%m-%dT%H:%M:%SZ')
      return attributes
      