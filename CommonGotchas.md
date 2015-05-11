### need private\_keys.py ###

Issue: You can't run the front end at all without getting a copy of private\_keys.py from an existing developer.

Solution:  Do some trickery to support local dev.  For example, have private\_keys.py actually checked in, and in local dev it would point to a test SOLR instance.  In production (e.g. on app engine) it would pull the keys from a $ENV\_keys.yaml file, where $ENV is determined using a combination of the CGI variables discussed [here](http://code.google.com/appengine/docs/python/runtime.html#The_Environment).

Requirements:  We need a 'publicly' addressable SOLR instance or proxy that we can reference in SVN.  We need to codify the environments (prod, qa, etc.) and bake a quick yaml format for the key files.

### Google Maps API keys hardcoded ###

Issue: The Google Maps API keys are hardcoded, and only work on production.

Solution: Pull the keys from $ENV\_keys.yaml file.

Requirements: Need to codify the environments and yaml format as above.

### Static HTML served from SVN trunk ###

Issue: SVN is being used as a simple CMS system in that static content is actually pulled from SVN trunk over HTTP (see [static\_content](http://code.google.com/p/allforgood/source/browse/trunk/frontend/views.py#1039)).  This prevents us from checking anything into trunk until it's been approved to go live, which causes issue with the standard workflow.

Solution: Using SVN as a CMS works well enough, but we should probably use a branch instead of trunk.  We will need to document merging the static content into the branch as part of the release process.  $ENV\_keys.yaml should probably include what branch to pull content from.

Requirements: Determine branch structure, document merge as part of release process.

### Frontend directory is very flat. ###

Issue: frontend has almost 20 subdirectories and 30+ files in it, and they are a mix of 1st party code, static content, and 3rd party projects.  This makes it really hard to explain/document the code.

Solution: Devise a new structured layout for the code, something like (just a quick first pass):

```
/frontend/
   /views/
      /static/
          /css/
          /html/
          /images/
          /js/
       /templates/
       /template_tags/
       /facebookapp/
       #break views.py into logical partitions, something like
       static_views.py
       admin.py
       redirects.py
       view_helpers.py
   /api/
      __init__.py (replaces api.py)
      /search/
      api_helpers.py
     views.py #contains API specific view handlers
   /util/
      /versioned_memcache/
   /thirdparty/
      /gdata/
      /recaptcha/
      /facebook/
      #all other 3rd party code we might want to use SVN links for
```