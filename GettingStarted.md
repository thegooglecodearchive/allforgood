# Introduction #

There are three major components to the dev environment:

  * The frontend, which includes the allforgood.org website and API data feeds.
  * The backend data loader, which converts volunteer opportunities in various formats into AfG's internal representation.
  * The backend SOLR server, which indexes and stores the opportunities for retrieval by the frontend.

Setting up each component will be discussed below.

## Downloading the code ##

All of the code is hosted on Google Code, and is available via SVN.

```
svn checkout http://allforgood.googlecode.com/svn/trunk/ allforgood
```

The code is broken into a several directories:

  * datahub - The backend data loading code.  See Backend Development below for more details.
  * etc - contains some extraneous SVN setup scripts.
  * frontend - contains the Google App Engine project for the frontend (website and API).  See Frontend Development below for more details.
  * site\_down - An alternative App Engine project for when AfG is in maintenance mode.
  * SOLR - the configuration files for the the SOLR Search Engine instance used by the backend.  See Backend Development below for more details.
  * spec - the specification for the Footprint XML format used to load volunteer opprotunities into All For Good.
  * tools - some tools for testing AfG quality.

# Getting Started with Frontend Development #

The frontend is a [Google App Engine](http://code.google.com/appengine/) project, written in Python.  Google App Engine applications can be worked on using the Google App Engine SDK, which is available for all major platforms.

## Setting up the Google App Engine SDK ##

Follow the Getting Started guide for the Google App Engine SDK, and [Download](http://code.google.com/appengine/downloads.html) the SDK for Python for your OS.

## Requirements for running the code. ##

Before you can run the frontend, you'll need to get a copy of private\_keys.py from an approved developer.  This file contains private information, and should not be checked into SVN.

If you just want to checkout the frontend (e.g. page layout) and are not interested in actually running queries, you can use the following as a skeleton private\_keys.py:

```
DEFAULT_FACEBOOK_SECRET = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxx'
DEFAULT_BACKEND_URL_SOLR = 'http://localhost:8983/solr/select/'
FACEBOOK_SECRETS = {}
AFG_GOOGLE_DOCS_LOGIN  = {
    'username' : 'username_here',
    'password' : 'password_here'
}
```

Save the above to frontend/private\_keys.py.  Some parts of the site should 'work', but the following functionality will not:

  * Facebook integration.
  * Search (unless you are running a SOLR server on localhost).

## The Frontend code structure ##

The frontend code is laid out as follows:

  * app.yaml/main.py/urls.py - Maps most incoming URLs to view handlers (see Views below).
  * views.py - This is where the meat of the frontend code lives (see Views below).
  * html/css/js/images - static content (actually served from SVN, see CommonGotchas).
  * templates - contains the Django templates (see Views below).
  * search.py/solr\_search.py - interacts with SOLR backend.
  * scoring.py - sorts the SOLR results.
  * api.py - Logic for API output.
  * everything else - there's a lot more code, too much to go into in this guide.

The above list should help get you pointed to the right spot.

### Views ###

The Views in AfG are a combination of:

- webapp [RequestHandler](http://code.google.com/appengine/docs/python/tools/webapp/requesthandlers.html) classes.
- url mappings in app.yaml and main.py
- Django templates.

The quick and dirty guide to how most URLs in AfG are handled:

  1. Incoming URL is matched in app.yaml (e.g. www.allforgood.org/search -> main.py at the very bottom of app.yaml (the default handler)).
  1. the appropriate python file is ran (in this case main.py).
  1. in the case of main.py, a list of urls from urls.py is mapped to a handler (e.g. (urls.URL\_CONSUMER\_UI\_SEARCH, views.consumer\_ui\_search\_view)).
  1. the get() method is called on the mapped request class (e.g. consumer\_ui\_search\_view).
  1. In most cases, a template is rendered using template\_helpers.render\_template().
    * render\_template() is passed in a template file path and an dictionary.
    * The templates are written in [Django](http://code.google.com/appengine/docs/python/gettingstarted/templates.html) and can refer to values in the passed in dictionary.
  1. the rendered template is written to the response.

#### Static Content ####

In addition to the dynamic views, there are also a fair number of static urls (see urls.py : STATIC\_CONTENT\_FILES).  These URLs are handled in a somewhat quirky way (as explained in CommonGotchas):  the handler (views.static\_content) actually retrieves the content directly from code.google.com (or a memcached copy) rather than the local appengine copy.  This acts as a simple CMS, in that changes can be made in SVN rather than requiring a code push to appengine.  If you are testing local changes to static files, you can use the "local" argument to use the appengine copy, e.g.:

`http://www.allforgood.org/about?local=1`

This tells static\_content to load the file directly rather than using SVN/memcache.

### The API ###

In addition to the end-user site, the primary goal of AfG is to expose an API for others to use to build volunteering applications upon.

The API is available at:

`http://www.allforgood.org/api/volopps`

The API supports the following formats:

  * [Atom](http://en.wikipedia.org/wiki/Atom_(standard))-formatted XML
  * JSON

The code flow for an API request is:

  1. Request comes in to /api
  1. Request is routed to views.search\_view by main.py/urls.py
  1. result\_set is created via search.search()
  1. search\_view.get() setups up arguments and instantiates an api\_writer object.
  1. api\_writer is used to output the result\_set in the correct format.

### Searching Volunteer Opportunities ###

At a high level, the search functionality of AfG looks like this:

  * Volunteer Opportunities are uploaded to SOLR via an offline process.
  * Search queries come in via the API or consumer site.
  * search.search() is called.
  * if the result is already in memcache it is returned.
  * otherwise SOLR is queried via solr\_search.search()
    * this builds a SOLR query via solr\_search.form\_solr\_query()
    * the query URL is access on the SOLR backend.
    * a result set is returned as JSON.
    * this is converted to a searchresult.SearchResultSet object in solr\_search.query()
  * the SearchResultSet is scored (ranked/sorted) via scoring.score\_result\_set().
  * duplicate results are removed via SearchResultSet.dedup()

# Getting started with Backend/Search Engine Development #

## Data loading code structure ##

The backend loading code is all in datahub, there's a [README](http://code.google.com/p/allforgood/source/browse/trunk/datahub/README) that explains what's going on at a high level.

The short version is that there's a demon process running on a box somewhere that sucks in feeds from our providers and converts it to our FootPrint XML format.  Then that data is uploaded into SOLR.

## SOLR Search Engine structure ##

The SOLR configuration files are stored in the [SOLR/conf](http://code.google.com/p/allforgood/source/browse/trunk/#trunk/SOLR/conf) folder.

In general, SOLR modifications are outside the scope of this document.  If you want to get a basic understanding of SOLR, check out the [tutorial](http://lucene.apache.org/solr/tutorial.html).

  * solrconfig.xml - basic configuration (cache sizes, etc.)
  * schema.xml - our SOLR schema.  Not quite the same as Footprint.


# Committing Code changes #

## Getting commit access ##

Here is the process to obtain commit access:
1. get trained: with the help of a mentor, pick a simple, suitable starter project.
2. check out the code in read-only mode and start up a server.  If you don't have an internet connection that supports inbound services, then upload your example server to appengine (yourappname.appspot.com)
3. implement your change.
4. get it reviewed.  Expect several rounds of pedantic reviews.
5. once reviewed, you'll be granted commit access.

## The code review process ##

(from the toplevel source directory)
> ./codereview\_upload.py username@gmail.com
where username is the reviewer.  Everything else is handled automatically-- for more info, see codereview\_upload.py, function main().

Note that you will need to install the pylint tool: http://pypi.python.org/pypi/pylint
and that we insist on a pylint score of 9.0 per file, rather than rely on fallible human reviewers.