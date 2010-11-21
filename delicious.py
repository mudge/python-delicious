#!/usr/bin/env python
"""Python-Delicious

Python module for access to del.icio.us <http://del.icio.us/> via its API.

Recommended: Python 2.3 or later (untested on previous versions)
"""

__version__ = "pre-1.0"
#__version__ = "1.0"
__license__ = "BSD"
__copyright__ = "Copyright 2005-2008, Paul Mucur"
__author__ = "Paul Mucur <http://mucur.name/>"

#TODO:
#   Should text be properly escaped for XML? Or that not this module's
#       responsibility?
#   Create test suite
#   Gzip support - but the API does not yet support it
#   Use Etags and Last-Modified to make requests more efficient - but the API
#       does not yet support it

_debug = 0

# The user agent string sent to del.icio.us when making requests. If you are
# using this module in your own application, you should probably change this.
USER_AGENT = "Python-Delicious/%s +http://github.com/mudge/python-delicious" % __version__

import urllib
import urllib2
import sys
import re
import time
from xml.dom import minidom
try:
    StringTypes = basestring
except:
    try:
        # Python 2.2 does not have basestring
        from types import StringTypes
    except:
        # Python 2.0 and 2.1 do not have StringTypes
        from types import StringType, UnicodeType
        StringTypes = None
try:
    ListType = list
    TupleType = tuple
except:
    from types import ListType, TupleType

# Taken from Mark Pilgrim's amazing Universal Feed Parser
# <http://feedparser.org/>
try:
    UserDict = dict
except NameError:
    from UserDict import UserDict
try:
    import datetime
except:
    datetime = None


# The URL of the del.icio.us API as it will be changing shortly.
DELICIOUS_API = "https://api.del.icio.us/v1"

def open(username, password):
    """Open a connection to a del.icio.us account"""
    return DeliciousAccount(username, password)

def connect(username, password):
    """Open a connection to a del.icio.us account"""
    return open(username, password)


# Custom exceptions

class DeliciousError(Exception):
    """Error in the Python-Delicious module"""
    pass

class ThrottleError(DeliciousError):
    """Error caused by del.icio.us throttling requests"""
    def __init__(self, url, message):
        self.url = url
        self.message = message
    def __str__(self):
        return "%s: %s" % (self.url, self.message)

class AddError(DeliciousError):
    """Error adding a post to del.icio.us"""
    pass

class DeleteError(DeliciousError):
    """Error deleting a post from del.icio.us"""
    pass

class BundleError(DeliciousError):
    """Error bundling tags on del.icio.us"""
    pass

class DeleteBundleError(DeliciousError):
    """Error deleting a bundle from del.icio.us"""
    pass

class RenameTagError(DeliciousError):
    """Error renaming a tag in del.icio.us"""
    pass

class DateParamsError(DeliciousError):
    '''Date params error'''
    pass

class DeliciousAccount(UserDict):
    """A del.icio.us account"""

    # Used to track whether all posts have been downloaded yet.
    __allposts = 0
    __postschanged = 0

    # Time of last request so that the one second limit can be enforced.
    __lastrequest = None

    # Special methods

    def __init__(self, username, password):
        UserDict.__init__(self)

        # Authenticate the URL opener so that it can access del.icio.us
        if _debug:
            sys.stderr.write("Initialising DeliciousAccount object.\n")
        auth_handler = urllib2.HTTPBasicAuthHandler()
        auth_handler.add_password("del.icio.us API", "https://api.del.icio.us/", \
                username, password)
        opener = urllib2.build_opener(auth_handler)
        opener.addheaders = [("User-agent", USER_AGENT)]
        urllib2.install_opener(opener)
        if _debug:
            sys.stderr.write("URL opener with HTTP authenticiation installed globally.\n")
        self["lastupdate"] = self.lastupdate()
        self["lastupdate_parsed"] = time.strptime(self["lastupdate"], \
                "%Y-%m-%dT%H:%M:%SZ")
        if _debug:
            sys.stderr.write("Time of last update loaded into class dictionary.\n")

    def __getitem__(self, key):
        try:
            return UserDict.__getitem__(self, key)
        except KeyError:
            if key == "tags":
                return self.tags()
            elif key == "dates":
                return self.dates()
            elif key == "posts":
                return self.posts()
            elif key == "bundles":
                return self.bundles()

    def __setitem__(self, key, value):
        if key == "posts":
            if _debug:
                sys.stderr.write("The value of posts has been changed.\n")
            self.__postschanged = 1
        return UserDict.__setitem__(self, key, value)


    def __request(self, url):

        # Make sure that it has been at least 1 second since the last
        # request was made. If not, halt execution for approximately one
        # seconds.
        if self.__lastrequest and (time.time() - self.__lastrequest) < 2:
            if _debug:
                sys.stderr.write("It has been less than two seconds since the last request; halting execution for one second.\n")
            time.sleep(1)
        if _debug and self.__lastrequest:
            sys.stderr.write("The delay between requests was %d.\n" % (time.time() - self.__lastrequest))
        self.__lastrequest = time.time()
        if _debug:
            sys.stderr.write("Opening %s.\n" % url)
        xml = urllib2.urlopen(url)
        self["headers"] = {}
        for header in xml.headers.headers:
            (name, value) = header.split(": ")
            self["headers"][name.lower()] = value[:-2]
        if xml.headers.status == "503":
            raise ThrottleError(url, \
                    "503 HTTP status code returned by del.icio.us")
        if _debug:
            sys.stderr.write("%s opened successfully.\n" % url)
        return minidom.parseString(xml.read())


    # Methods to fetch del.icio.us content

    def lastupdate(self):
        """Return the last time that the del.icio.us account was updated."""
        return self.__request("%s/posts/update" % \
                DELICIOUS_API).firstChild.getAttribute("time")

    def posts(self, tag="", date="", todt="", fromdt="", count=0):
        """Return del.icio.us bookmarks as a list of dictionaries.

        This should be used without arguments as rarely as possible by
        combining it with the lastupdate attribute to only get all posts when
        there is new content as it places a large load on the del.icio.us
        servers.

        """
        query = {}

        ## if a date is passed then a ranged set of date params CANNOT be passed
        if date and (todt or fromdt):
            raise DateParamsError

        if not count and not date and not todt and not fromdt and not tag:
            path = "all"

            # If attempting to load all of the posts from del.icio.us, and
            # a previous download has been done, check to see if there has
            # been an update; if not, then just return the posts stored
            # inside the class.
            if _debug:
                sys.stderr.write("Checking to see if a previous download has been made.\n")
            if not self.__postschanged and self.__allposts and \
                    self.lastupdate() == self["lastupdate"]:
                if _debug:
                    sys.stderr.write("It has; returning old posts instead.\n")
                return self["posts"]
            elif not self.__allposts:
                if _debug:
                    sys.stderr.write("Making note of request for all posts.\n")
                self.__allposts = 1
        elif date:
            path = "get"
        elif todt or fromdt:
            path = "all"
        else:
            path = "recent"
        if count:
            query["count"] = count
        if tag:
            query["tag"] = tag

        ##todt
        if todt and (isinstance(todt, ListType) or isinstance(todt, TupleType)):
            query["todt"] = "-".join([str(x) for x in todt[:3]])
        elif todt and (todt and isinstance(todt, datetime.datetime) or \
                isinstance(todt, datetime.date)):
            query["todt"] = "-".join([str(todt.year), str(todt.month), str(todt.day)])
        elif todt:
            query["todt"] = todt

        ## fromdt
        if fromdt and (isinstance(fromdt, ListType) or isinstance(fromdt, TupleType)):
            query["fromdt"] = "-".join([str(x) for x in fromdt[:3]])
        elif fromdt and (fromdt and isinstance(fromdt, datetime.datetime) or \
                isinstance(fromdt, datetime.date)):
            query["fromdt"] = "-".join([str(fromdt.year), str(fromdt.month), str(fromdt.day)])
        elif fromdt:
            query["fromdt"] = fromdt

        if date and (isinstance(date, ListType) or isinstance(date, TupleType)):
            query["dt"] = "-".join([str(x) for x in date[:3]])
        elif date and (datetime and isinstance(date, datetime.datetime) or \
                isinstance(date, datetime.date)):
            query["dt"] = "-".join([str(date.year), str(date.month), str(date.day)])
        elif date:
            query["dt"] = date

        postsxml = self.__request("%s/posts/%s?%s" % (DELICIOUS_API, path, \
                urllib.urlencode(query))).getElementsByTagName("post")
        posts = []
        if _debug:
            sys.stderr.write("Parsing posts XML into a list of dictionaries.\n")

        # For each post, extract every attribute (splitting tags into sub-lists)
        # and insert as a dictionary into the `posts` list.
        for post in postsxml:
            postdict = {}
            for (name, value) in post.attributes.items():
                if name == u"tag":
                    name = u"tags"
                    value = value.split(" ")
                if name == u"time":
                    postdict[u"time_parsed"] = time.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
                postdict[name] = value
            if self.has_key("posts") and isinstance(self["posts"], ListType) \
                    and postdict not in self["posts"]:
                self["posts"].append(postdict)
            posts.append(postdict)
        if _debug:
            sys.stderr.write("Inserting posts list into class attribute.\n")
        if not self.has_key("posts"):
            self["posts"] = posts
        if _debug:
            sys.stderr.write("Resetting marker so module doesn't think posts has been changed.\n")
        self.__postschanged = 0
        return posts

    def tags(self):
        """Return a dictionary of tags with the number of posts in each one"""
        tagsxml = self.__request("%s/tags/get?" % \
                DELICIOUS_API).getElementsByTagName("tag")
        tags = []
        if _debug:
            sys.stderr.write("Parsing tags XML into a list of dictionaries.\n")
        for tag in tagsxml:
            tagdict = {}
            for (name, value) in tag.attributes.items():
                if name == u"tag":
                    name = u"name"
                elif name == u"count":
                    value = int(value)
                tagdict[name] = value
            if self.has_key("tags") and isinstance(self["tags"], ListType) \
                    and tagdict not in self["tags"]:
                self["tags"].append(tagdict)
            tags.append(tagdict)
        if _debug:
            sys.stderr.write("Inserting tags list into class attribute.\n")
        if not self.has_key("tags"):
            self["tags"] = tags
        return tags

    def bundles(self):
        """Return a dictionary of all bundles"""
        bundlesxml = self.__request("%s/tags/bundles/all" % \
                DELICIOUS_API).getElementsByTagName("bundle")
        bundles = []
        if _debug:
            sys.stderr.write("Parsing bundles XML into a list of dictionaries.\n")
        for bundle in bundlesxml:
            bundledict = {}
            for (name, value) in bundle.attributes.items():
                bundledict[name] = value
            if self.has_key("bundles") and isinstance(self["bundles"], ListType) \
                    and bundledict not in self["bundles"]:
                self["bundles"].append(bundledict)
            bundles.append(bundledict)
        if _debug:
            sys.stderr.write("Inserting bundles list into class attribute.\n")
        if not self.has_key("bundles"):
            self["bundles"] = bundles
        return bundles

    def dates(self, tag=""):
        """Return a dictionary of dates with the number of posts at each date"""
        if tag:
            query = urllib.urlencode({"tag":tag})
        else:
            query = ""
        datesxml = self.__request("%s/posts/dates?%s" % \
                (DELICIOUS_API, query)).getElementsByTagName("date")
        dates = []
        if _debug:
            sys.stderr.write("Parsing dates XML into a list of dictionaries.\n")
        for date in datesxml:
            datedict = {}
            for (name, value) in date.attributes.items():
                if name == u"date":
                    datedict[u"date_parsed"] = time.strptime(value, "%Y-%m-%d")
                elif name == u"count":
                    value = int(value)
                datedict[name] = value
            if self.has_key("dates") and isinstance(self["dates"], ListType) \
                    and datedict not in self["dates"]:
                self["dates"].append(datedict)
            dates.append(datedict)
        if _debug:
            sys.stderr.write("Inserting dates list into class attribute.\n")
        if not self.has_key("dates"):
            self["dates"] = dates
        return dates


    # Methods to modify del.icio.us content

    def add(self, url, description, extended="", tags=(), date=""):
        """Add a new post to del.icio.us"""
        query = {}
        query["url"] = url
        query ["description"] = description
        if extended:
            query["extended"] = extended
        if tags and (isinstance(tags, TupleType) or isinstance(tags, ListType)):
            query["tags"] = " ".join(tags)
        elif tags and (StringTypes and isinstance(tags, StringTypes)) or \
                (not StringTypes and (isinstance(tags, StringType) or \
                isinstance(tags, UnicodeType))):
            query["tags"] = tags

        # This is a rather rudimentary way of parsing date strings into
        # ISO8601 dates: if the date string is shorter than the required
        # 20 characters then it is assumed that it is a partial date
        # such as "2005-3-31" or "2005-3-31T20:00" and it is split into a
        # list along non-numerals. Empty elements are then removed
        # and then this is passed to the tuple/list case where
        # the tuple/list is padded with necessary 0s and then formatted
        # into an ISO8601 date string. This does not take into account
        # time zones.
        if date and (StringTypes and isinstance(tags, StringTypes)) or \
                (not StringTypes and (isinstance(tags, StringType) or \
                isinstance(tags, UnicodeType))) and len(date) < 20:
            date = re.split("\D", date)
            while '' in date:
                date.remove('')
        if date and (isinstance(date, ListType) or isinstance(date, TupleType)):
            date = list(date)
            if len(date) > 2 and len(date) < 6:
                for i in range(6 - len(date)):
                    date.append(0)
            query["dt"] = "%.4d-%.2d-%.2dT%.2d:%.2d:%.2dZ" % tuple(date)
        elif date and (datetime and (isinstance(date, datetime.datetime) \
                or isinstance(date, datetime.date))):
            query["dt"] = "%.4d-%.2d-%.2dT%.2d:%.2d:%.2dZ" % date.utctimetuple()[:6]
        elif date:
            query["dt"] = date
        try:
            response = self.__request("%s/posts/add?%s" % (DELICIOUS_API, \
                    urllib.urlencode(query)))
            if response.firstChild.getAttribute("code") != u"done":
                raise AddError
            if _debug:
                sys.stderr.write("Post, %s (%s), added to del.icio.us\n" \
                        % (description, url))
        except:
            if _debug:
                sys.stderr.write("Unable to add post, %s (%s), to del.icio.us\n" \
                        % (description, url))

    def bundle(self, bundle, tags):
        """Bundle a set of tags together"""
        query = {}
        query["bundle"] = bundle
        if tags and (isinstance(tags, TupleType) or isinstance(tags, ListType)):
            query["tags"] = " ".join(tags)
        elif tags and isinstance(tags, StringTypes):
            query["tags"] = tags
        try:
            response = self.__request("%s/tags/bundles/set?%s" % (DELICIOUS_API, \
                    urllib.urlencode(query)))
            if response.firstChild.getAttribute("code") != u"done":
                raise BundleError
            if _debug:
                sys.stderr.write("Tags, %s, bundled into %s.\n" \
                        % (repr(tags), bundle))
        except:
            if _debug:
                sys.stderr.write("Unable to bundle tags, %s, into %s to del.icio.us\n" \
                        % (repr(tags), bundle))

    def delete(self, url):
        """Delete post from del.icio.us by its URL"""
        try:
            response = self.__request("%s/posts/delete?%s" % (DELICIOUS_API, \
                    urllib.urlencode({"url":url})))
            if response.firstChild.getAttribute("code") != u"done":
                raise DeleteError
            if _debug:
                sys.stderr.write("Post, %s, deleted from del.icio.us\n" \
                        % url)
        except:
            if _debug:
                sys.stderr.write("Unable to delete post, %s, from del.icio.us\n" \
                    % url)

    def delete_bundle(self, name):
        """Delete bundle from del.icio.us by its name"""
        try:
            response = self.__request("%s/tags/bundles/delete?%s" % (DELICIOUS_API, \
                    urllib.urlencode({"bundle":name})))
            if response.firstChild.getAttribute("code") != u"done":
                raise DeleteBundleError
            if _debug:
                sys.stderr.write("Bundle, %s, deleted from del.icio.us\n" \
                        % name)
        except:
            if _debug:
                sys.stderr.write("Unable to delete bundle, %s, from del.icio.us\n" \
                    % name)

    def rename_tag(self, old, new):
        """Rename a tag"""
        query = {"old":old, "new":new}
        try:
            response = self.__request("%s/tags/rename?%s" % (DELICIOUS_API, \
                    urllib.urlencode(query)))
            if response.firstChild.getAttribute("code") != u"done":
                raise RenameTagError
            if _debug:
                sys.stderr.write("Tag, %s, renamed to %s\n" \
                        % (old, new))
        except:
            if _debug:
                sys.stderr.write("Unable to rename %s tag to %s in del.icio.us\n" \
                    % (old, new))

if __name__ == "__main__":
    if sys.argv[1:][0] == '-v' or sys.argv[1:][0] == '--version':
        print __version__

#REVISION HISTORY
#0.1 - 29/3/2005 - PEM - Initial version.
#0.2 - 30/3/2005 - PEM - Now using urllib's urlencode to handle query building
#   and the class now extends dict (or failing that: UserDict).
#0.3 - 30/3/2005 - PEM - Rewrote doc strings and improved the metaphor that the
#   account is a dictionary by adding posts, tags and dates to the account
#   object when they are called. This has the added benefit of reducing
#   requests to del.icio.us as one need only call posts(), dates() and tags()
#   once and they are stored inside the class instance until deletion.
#0.4 - 30/3/2005 - PEM - Added private __request method to handle URL requests
#   to del.icio.us and implemented throttle detection.
#0.5 - 30/3/2005 - PEM - Now implements every part of the API specification
#0.6 - 30/3/2005 - PEM - Heavily vetted code to conform with PEP 8: use of
#   isinstance(), use of `if var` and `if not var` instead of comparison to
#   empty strings and changed all string delimiters to double primes for
#   consistency.
#0.7 - 31/3/2005 - PEM - Made it so that when a fetching operation such as
#   posts() or tags() is used, only new posts are added to the class dictionary
#   in part to increase efficiency and to prevent, say, an all posts call of
#   posts() being overwritten by a specific request such as posts(tag="ruby")
#   Added more intelligent date handling for adding posts; will now attempt to
#   format any *reasonable* string, tuple or list into an ISO8601 date. Also
#   changed the command to get the lastupdate as it was convoluted. The
#   all posts command now checks to see if del.icio.us has been updated since
#   it was last called, again, this is to reduce the load on the servers and
#   increase speed a little. Changed the version string to a pre-1.0 release
#   Subversion-generated one because I am lazy.
#0.8 - 1/4/2005 - PEM - Improved intelligence of posts caching: will only
#   re-download all posts if the posts attribute has been changed. Added
#   the mandatory delay between requests of at least one second. Changed the
#   crude string replace method to encode ampersands with a more intelligent
#   regular expression.
#0.9 - 2/4/2005 - PEM - Now uses datetime objects when possible.
#0.10 - 4/4/2005 - PEM - Uses the time module when the datetime module is
#   unavailable (such as versions of Python prior to 2.3). Now uses time
#   tuples instead of datetime objects when outputting for compatibility and
#   consistency. Time tuples are a new attribute: "date_parsed", with the
#   original string format of the date (or datetime) in "date" etc. Now stores
#   the headers of each request.
