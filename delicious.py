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
        '''Return a dictionary containing the last update time for the user and the number of new items in the user's inbox since it was last visited.

        Returns: dict

        '''
        response, content = self.h.request('https://api.del.icio.us/v1/posts/update')
        if response.status == 200:

            # Make a copy of the attributes.
            attributes = self.__convert_time_string(dict(etree.fromstring(content).attrib))
            return attributes

    def recent_bookmarks(self, count=None, tag=None):
        '''Return a list of the most recent bookmarks.

        Keyword arguments:
        count -- the number of bookmarks to return (default is 15, maximum is 100)
        tag -- a specific tag to filter by

        Returns: list

        '''
        parameters = {}
        if count:
            parameters['count'] = count
        if tag:
            parameters['tag'] = tag
        response, content = self.h.request('https://api.del.icio.us/v1/posts/recent?' + urlencode(parameters))
        if response.status == 200:
            bookmarks = [self.__convert_time_string(dict(post.attrib)) for post in etree.fromstring(content).findall('post')]
            return bookmarks

    def delete_bookmark(self, url):
        '''Delete a specific bookmark by URL.

        Keyword arguments:
        url -- the URL of the bookmark to delete

        Returns: string
        '''
        response, content = self.h.request('https://api.del.icio.us/v1/posts/delete?' + urlencode({'url': url}))
        if response.status == 200:
            return etree.fromstring(content).attrib['code']
    
    def bookmark(self, tags=None, date=None, url=None, hashes=None, meta=None):
        '''Return one or more bookmarks on a single day matching the given parameters.
        
        Keyword arguments:
        tags -- filter by a space-separated list of tags
        date -- filter by this datetime (defaults to most recent date on which bookmarks were saved)
        url -- filter by URL regardless of date
        hashes -- fetch multiple bookmarks by URL MD5s regardless of date
        meta -- include change detection signature on each item in a 'meta' attribute
        
        '''
        parameters = {}
        if tags:
            parameters['tag'] = tags
        if date:
            parameters['dt'] = date.isoformat() + 'Z'
        if url:
            parameters['url'] = url
        if hashes:
            parameters['hashes'] = hashes
        if isinstance(meta, bool):
            if meta:
                parameters['meta'] = 'yes'
            else:
                parameters['meta'] = 'no'
        response, content = self.h.request('https://api.del.icio.us/v1/posts/get?' + urlencode(parameters))
        if response.status == 200:
            bookmarks = [self.__convert_time_string(dict(post.attrib)) for post in etree.fromstring(content).findall('post')]
            return bookmarks
        
    def __convert_time_string(self, dict_with_time, time_key='time'):
        '''Convert an ISO8601 time string to a datetime in a dictionary.

        Keyword arguments:
        dict_with_time -- the dictionary with the time string
        time_key -- the key in the dictionary holding the time string (default is 'time')

        '''
        dict_with_time[time_key] = datetime.datetime.strptime(dict_with_time[time_key], '%Y-%m-%dT%H:%M:%SZ')
        return dict_with_time