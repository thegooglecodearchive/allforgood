## Code Flow ##

  * Client requests a page (e.g. GET /about)
  * AppEngine framework searches app.yaml for appropriate python file.
  * Python file is loaded, and main is executed.
  * main sets up a WSGIApplication with a list of URL regex's to handle.
  * If a regex matches, the corresponding RequestHandler is used.
  * RequestHandler's appropriate method is called (e.g. GET request maps to .get(), POST to .post(), etc.).
  * RequestHandler writes an appropriate response to the client.

## Templates ##

Most of the UI views in views.py are rendered using Django Templates.

For example:

```
class my_events_view(webapp.RequestHandler):
  """Shows events that you and your friends like or are doing."""
  @expires(0)  # User specific.
  def get(self):
    """HTTP get method."""
    template_values = get_default_template_values(self.request, 'MY_EVENTS')
    if not template_values['user']:
      template_values = {
        'current_page': 'MY_EVENTS',
        # Don't bother rendering this page if not authenticated.
        'redirect_to_home': True,
      }
      self.response.out.write(render_template(MY_EVENTS_TEMPLATE,
          template_values))
      return
    self.response.out.write(render_template(MY_EVENTS_TEMPLATE,
                                            template_values))
```

Django Templates are rendered using the render\_template() helper method from template\_helpers.py.  It is passed the filename for a template, and a dictionary of template values.  Control codes in the template are replaced with appropriate values from the dictionary.  For example:

```
{% for result in result_set.clipped_results %}
  <div class='snippet'>
    <table class='snippet_table'>
    <tr>
    <td valign='top' class='snippet_number'>
      {{ forloop.counter0|as_letter }}
    </td>

    <td valign='top'>
    <div>
      {# TODO(paul): ESCAPE THE LOCATION FIELD AGAINST QUOTES #}
      {% if result.latlong %}
        <script type='text/javascript'>
          asyncLoadManager.addCallback('map', function() {
            var coords = '{{result.latlong}}'.split(',');
            map.addMarker(
                coords[0], coords[1], '{{ forloop.counter0|as_letter }}');
          });
        </script>
      {% endif %}

      ...
{endfor}
```

This code iterates through each object in the clipped\_results array, and builds a series of nested divs.  See the [Django Template docs](http://www.djangoproject.com/documentation/0.96/templates/) for more information on the template system.

## Static Content ##

In addition to the dynamic views, there are also a fair number of static urls (see urls.py : STATIC\_CONTENT\_FILES). These URLs are handled in a somewhat quirky way (as explained in CommonGotchas): the handler (views.static\_content) actually retrieves the content directly from code.google.com (or a memcached copy) rather than the local appengine copy. This acts as a simple CMS, in that changes can be made in SVN rather than requiring a code push to appengine. If you are testing local changes to static files, you can use the "local" argument to use the appengine copy, e.g.:

http://www.allforgood.org/about?local=1

This tells static\_content to load the file directly rather than using SVN/memcache.