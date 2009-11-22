import httplib2
import datetime
from urllib.parse import urlencode
try:
    from lxml import etree
except ImportError:
    import xml.etree.ElementTree as etree

class Account:
    
    '''A user account for Delicious.'''
    
    _last_updated = None
    _bookmarks = []
    
    def __init__(self, username, password, http_cache='.cache'):
        '''Return a Delicious account.
        
        Keyword arguments:
        username -- the username of the user
        password -- the password of the user
        http_cache -- where to store the httplib2 cache (default is '.cache')
        
        Returns: Account
        
        '''
        self.username = username
        self.password = password
        self.h = httplib2.Http(http_cache)
        self.h.add_credentials(username, password, 'api.del.icio.us')

    def last_update(self):
        '''Return a dictionary containing the last update time for the user and the number of new items in the user's inbox since it was last visited.

        Returns: dict

        '''
        response, content = self.h.request('https://api.del.icio.us/v1/posts/update')
        if response.status == 200:
            attributes = self.__convert_time_string(dict(etree.fromstring(content).attrib))
            return attributes

    def recent(self, count=None, tag=None):
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

    def delete(self, url):
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
        tags -- filter by a list of tags
        date -- filter by this datetime (defaults to most recent date on which bookmarks were saved)
        url -- filter by URL regardless of date
        hashes -- fetch multiple bookmarks by URL MD5s regardless of date
        meta -- include change detection signature on each item in a 'meta' attribute
        
        Returns: list
        
        '''
        parameters = {}
        if tags:
            if isinstance(tags, list):
                parameters['tag'] = ' '.join(tags)
            elif isinstance(tags, str):
                parameters['tag'] = tags
        if date:
            if isinstance(date, datetime.date):
                parameters['dt'] = date.isoformat() + 'Z'
            elif isinstance(date, str):
                parameters['dt'] = date
        if url:
            parameters['url'] = url
        if hashes:
            if isinstance(hashes, list):
                parameters['hashes'] = ' '.join(hashes)
            elif isinstance(hashes, str):
                parameters['hashes'] = hashes
        if meta:
            parameters['meta'] = 'yes'
        response, content = self.h.request('https://api.del.icio.us/v1/posts/get?' + urlencode(parameters))
        if response.status == 200:
            bookmarks = [self.__convert_time_string(dict(post.attrib)) for post in etree.fromstring(content).findall('post')]
            return bookmarks
    
    def add(self, url, description, extended=None, tags=None, date=None, replace=None, private=None):
        '''Add a bookmark.
        
        Keyword arguments:
        url -- the URL of the bookmark
        description -- the description of the bookmark
        extended -- extra notes for the bookmark
        tags -- tags for the bookmark
        date -- datetime of the item
        replace -- whether to replace a bookmark if one already exists with the same URL
        private -- whether to make the bookmark private
        
        Returns the status code returned by Delicious as a string.
        
        '''
        parameters = {'url': url, 'description': description}
        if extended:
            parameters['extended'] = extended
        if tags:
            if isinstance(tags, list):
                parameters['tags'] = ' '.join(tags)
            elif isinstance(tags, str):
                parameters['tags'] = tags
        if date:
            if isinstance(date, datetime):
                parameters['date'] = date.isoformat()
            elif isinstance(date, str):
                parameters['date'] = date
        if replace is False:
            parameters['replace'] = 'no'
        if shared is False:
            parameters['shared'] = 'no'
        
        response, content = self.h.request('https://api.del.icio.us/v1/posts/add?' + urlencode(parameters))
        if response.status == 200:
            return etree.fromstring(content).attrib['code']
    
    def dates(self, tag=None):
        '''Return a list of dates with the number of posts on each date.
        
        Keyword arguments:
        tag -- tag to filter by
        
        Returns: list
        
        '''
        parameters = {}
        if tag:
            parameters['tag'] = tag
        response, content = self.h.request('https://api.del.icio.us/v1/posts/dates?' + urlencode(parameters))
        if response.status == 200:
            return [self.__convert_date_string(dict(date.attrib)) for date in etree.fromstring(content).findall('date')]
    
    def bookmarks(self, tag=None, offset=None, limit=None, from_=None, to=None, meta=None):
        '''Returns all bookmarks.
        
        Keyword arguments:
        tag -- filter by this tag
        offset -- start returning bookmarks this many results into the set
        limit -- only return this amount of results
        from -- only bookmarks on or after this date
        to -- only bookmarks on or before this date
        meta -- include change detection signatures
        
        Returns: list
        
        '''
        parameters = {}
        if tag:
            parameters['tag'] = tag
        if offset:
            parameters['start'] = offset
        if limit:
            parameters['results'] = limit
        if from_:
            if isinstance(from_, datetime.date):
                parameters['fromdt'] = from_.isoformat() + 'Z'
            elif isinstance(from_, str):
                parameters['fromdt'] = from_
        if to:
            if isinstance(to, datetime.date):
                parameters['todt'] = to.isoformat() + 'Z'
            elif isinstance(to, str):
                parameters['todt'] = to
        if meta:
            parameters['meta'] = 'yes'
        
        if self._last_updated is None or self._last_updated > self.last_update()['time']:
            response, content = self.h.request('https://api.del.icio.us/v1/posts/all?' + urlencode(parameters))
            if response.status == 200:
                self._last_updated = self.last_update()['time']
                self._bookmarks = [self.__convert_time_string(dict(post.attrib)) for post in etree.fromstring(content).findall('post')]
                return self._bookmarks
        else:
            return self._bookmarks
    
    def hashes(self):
        '''Return a change manifest of all bookmarks.'''
        response, content = self.h.request('https://api.del.icio.us/v1/posts/all?hashes')
        if response.status == 200:
            return [dict(post.attrib) for post in etree.fromstring(content).findall('post')]
    
    def suggest(self, url):
        '''Return a tuple of popular, recommended and network tags for a URL.'''
        response, content = self.h.request('https://api.del.icio.us/v1/posts/suggest?' + urlencode({'url': url}))
        if response.status == 200:
            popular = [tag.text for tag in etree.fromstring(content).findall('popular')]
            recommended = [tag.text for tag in etree.fromstring(content).findall('recommended')]
            network = [tag.text for tag in etree.fromstring(content).findall('network')]
            return (popular, recommended, network)
    
    def tags(self):
        '''Return a list of tags and number of times used by a user.'''
        response, content = self.h.request('https://api.del.icio.us/v1/tags/get')
        if response.status == 200:
            return [tag.attrib for tag in etree.fromstring(content).findall('tag')]
    
    def delete_tag(self, tag):
        '''Delete an existing tag.'''
        response, content = self.h.request('https://api.del.icio.us/v1/tags/delete?' + urlencode({'tag': tag}))
        if response.status == 200:
            return etree.fromstring(content).text
    
    def bundles(self, name=None):
        '''Return all bundles for a user.'''
        parameters = {}
        if name:
            parameters['bundle'] = name
        response, content = self.h.request('https://api.del.icio.us/v1/tags/bundles/all?' + urlencode(parameters))
        if response.status == 200:
            return [bundle.attrib for bundle in etree.fromstring(content).findall('bundle')]
            
    def set_bundle(self, name, tags):
        '''Assign a set of tags to a bundle.'''
        parameters = {'bundle': name}
        if isinstance(tags, list):
            parameters['tags'] = ' '.join(tags)
        elif isinstance(tags, str):
            parameters['tags'] = tags
        response, content = self.h.request('https://api.del.icio.us/v1/tags/bundles/set?' + urlencode(parameters))
        if response.status == 200:
            return etree.fromstring(content).text
    
    def delete_bundle(self, name):
        '''Delete a bundle.'''
        parameters = {'bundle': name}
        if response.status == 200:
            return etree.fromstring(content).text
            
    def rename_tag(self, old, new):
        '''Rename an existing tag.'''
        response, content = self.h.request('https://api.del.icio.us/v1/tags/rename?' + urlencode({'old': old, 'new': new}))
        if response.status == 200:
            return etree.fromstring(content).text
        
    def __convert_time_string(self, dict_with_time, time_key='time'):
        '''Convert an ISO8601 time string to a datetime in a dictionary.

        Keyword arguments:
        dict_with_time -- the dictionary with the time string
        time_key -- the key in the dictionary holding the time string (default is 'time')
        
        Returns: dict
        
        '''
        dict_with_time[time_key] = datetime.datetime.strptime(dict_with_time[time_key], '%Y-%m-%dT%H:%M:%SZ')
        return dict_with_time
        
    def __convert_date_string(self, dict_with_date, date_key='date'):
        '''Convert a hyphen-separated date string to a datetime in a dictionary.
        
        Keyword arguments:
        dict_with_date -- the dictionary with the date string
        date_key -- the key in the dictionary holding the date string (default is 'date')
        
        Returns: dict
        
        '''
        year, month, day = [int(x) for x in dict_with_date[date_key].split('-')]
        dict_with_date[date_key] = datetime.date(year, month, day)
        return dict_with_date
        
    def __convert_tag_string(self, dict_with_tags, tag_key='tags'):
        '''Convert a space-separated tag string to a list of tags.'''
        dict_with_tags['tags'] = dict_with_tags['tags'].split(' ')
        return dict_with_tags
