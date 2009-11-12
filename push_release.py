#!/usr/bin/python
#
# Copyright 2009 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Script to push app to App Engine

Does the following:
* Checks out a branch from SVN
* Sets the app name and optionally version in the app.yaml file
* Copies the private_keys.py file into the directory
* Runs appcfg.py to deploy the app
* Attempts to run the apps self test
* Opens the Dashboard for the app in your web browser
"""

import os
import sys
import subprocess
import urllib2
import optparse
import time
import webbrowser
import shutil

import getpass

SVN_URL = 'http://allforgood.googlecode.com/svn/'

def run_option_parser():
  """Configure and run the options parser"""
  
  #
  # Set up the parser and options
  #
  
  parser = optparse.OptionParser(usage="Usage: %prog [options] app-name")
  parser.add_option("--branch", dest="branch", default="trunk",
    help="Branch to check out from SVN, eg branches/release_alpha_0509. " +
      "Default is trunk.")
      
  parser.add_option("--private_key", dest="private_key", 
    default="frontend/private_keys.py",
    help="Filename to copy private key file from. Default is " +
      "frontend/private_keys.py")
      
  parser.add_option("--version", dest="version", default=None,
    help="Version string to pass to place in app.yaml and send to App " +
      "Engine. If not specified will use what's in the YAML file.")
      
  parser.add_option("--from-here", 
    action="store_true", dest="from_here", default=True,
    help="Push local app in frontend/ instead of from SVN.")
  
  parser.add_option("--email", dest="user_email", default=None,
    help="Email address to use for app engine login")

  # parser.add_option("--password", dest="user_passwd", default=None,
  #   help="Password to use for app engine login. If not specified will be" +
  #     "prompted for.")
  # See TODO below
  
  parser.add_option("--no-dash", dest="open_dashboard", default=False,
    action="store_false",
    help="Do not open app dashboard in browser after pushing the release.")

  parser.add_option("--dry-run", dest="for_real", default=True,
    action="store_false",
    help="Do not run appcfg.py or flush cache, but do everything else.")
  options, arguments = parser.parse_args()

  #
  # Validate options
  #

  # If they specified a branch, turn off --from-here
  if options.branch != 'trunk':
    options.from_here = False
  
  # App name must be specified if from SVN
  if len(arguments)<1 and not options.from_here:
    print "App name required"
    print parser.print_help()
    sys.exit(-1)
  
  # Get users password if not specified
  # if options.user_passwd==None:
  #  options.user_passwd = getpass.getpass("Password for %s:" % options.user_email)
  # TODO(jblocksom): Send password on stdin to appcfg.py

  return (options, arguments)


def export_svn_branch(branch_name):
  """Retrieve SVN branch code and returns the directory it was exported to.
  
  Arguments:
    branch_name is the name of the SVN branch, eg branches/release1, branches/release2, etc
    svn_url is the base URL for the SVN tree
  
  Return value:
    directory name the SVN branch was exported to.
  """
  # Just grab the /frontend part, that's all we need to deploy.
  url = SVN_URL + branch_name + '/frontend'
  
  # Directory name to export to: deploy_branch-name_YYYYMMDDTHHMMSS
  exported_dir = 'deploy_'
  exported_dir += branch_name.split('/')[-1]
  exported_dir += '_' + time.strftime('%Y%d%mT%H%M%S')
  
  cmd = 'svn export %s %s' % (url, exported_dir)
  print 'Running', cmd
  subprocess.call(cmd, shell=True)
  print 'SVN export complete'
  return exported_dir

def get_branch_revision(branch_name):
  """Figure out the revision number (eg 'r241') from SVN for a given branch."""

  url = SVN_URL + branch_name + '/frontend'
  cmd = 'svn info %s' % url
  print 'Running "' + cmd + '" to find revision number'
  info_proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
  info_results = info_proc.communicate()[0]

  # svn info command will print out a line like
  # Last Changed Rev: NNN
  # Grab the NNN and turn it into a string like rNNN
  for line in info_results.split('\n'):
    if line.startswith('Last Changed Rev:'):
      last_rev_str = line.split(':')[1].strip()

  print 'Last revision of', branch_name, 'is', last_rev_str
  return 'r' + last_rev_str


def get_keyfile(location, release_dir):
  """Copy the private_keys.py file from the specified location."""
  dst = os.path.join(release_dir, 'private_keys.py')
  print 'Copying private keys file from %s to %s' % (location, dst)
  shutil.copy2(location, dst)


def verify_keyfile(release_dir):
  """Return True if the private_keys.py file exists"""
  return os.path.exists(os.path.join(release_dir, 'private_keys.py'))

def get_app_from_yaml(release_dir):
  """Return app and version from yaml file"""
  app_yaml = open(os.path.join(release_dir, 'app.yaml'))
  app = ''
  version = ''
  for line in app_yaml:
    if line.startswith('application:'):
      app = line.split(':')[1].strip()
    if line.startswith('version:'):
      version = line.split(':')[1].strip()
 
  return (app, version)

def push_app(release_dir, app_name=None, app_version=None, for_real=False):
  """Update the code on App Engine using the appcfg.py program"""
  cmd_args = ['appcfg.py', 'update', release_dir]
  if app_name:
    cmd_args.insert(2, '--application=' + app_name)
  if app_version:
    cmd_args.insert(2, '--version=' + app_version)

  # subprocess can take a list of arguments, but for some reason 
  # appcfg.py doesn't like them. So just make a command line.
  cmd = ' '.join(cmd_args)
  print 'Uploading to appengine with command', cmd

  if for_real:
    # Set shell=True because appcfg.py is probably in /usr/local
    return subprocess.call(cmd, shell=True)
  else:
    return 0

def run_self_tests(app_name):
  """Attempt to run the app self tests."""
  # A problem with App Engine is that you can't figure out the URL from
  # the information in the configuration file. So we hardcode some of 
  # the URLs and construct a guess based on using appspot.com if it's
  # not in the hard coded list.
  base_app_urls = {
    'servicefootprint': 'http://allforgood.org/',
  }
  
  default_base_url = 'http://' + app_name + '.appspot.com/'
  app_url = base_app_urls.get(app_name, default_base_url)
  self_test_url = app_url + 'testapi/run?cache=0'
  
  # Self tests return HTTP code 500 if they don't pass and 200 if they're OK
  # urllib2 will throw an exception if it's 500, so grab that and display
  # an error. Otherwise assume it's OK.
  try:
    print 'Trying to run self test at', self_test_url
    test_result = urllib2.urlopen(self_test_url)
    test_result.read()
    print "Self test passed"
    return True
  except urllib2.HTTPError, err:
    if err.code == 500:
      print "Self tests did not all pass -- error 500"
      # Someday it might be nice to be figure out which tests failed here
    else:
      print 'Error ', err.code, 'retrieving self test URL', self_test_url
  except urllib2.URLError, err:
    print 'Error trying to retrieve self test URL:', err.reason

  return False

def open_dashboard(app_name):
  """Open App Engine versions dashboard for the user to verify deployment"""
  url = "http://appengine.google.com/deployment?&app_id=" + app_name
  webbrowser.open_new_tab(url)

def main():
  """Run everything."""
  
  # Parse command line options
  options, arguments = run_option_parser()

  #
  # Export from SVN or 
  if options.from_here:
    # Use local -- probably for testing. Don't change app name or version.
    release_dir = 'frontend'
    app_name, version = get_app_from_yaml(release_dir)
    if not options.version:
      options.version = version
    
  else:
    app_name = arguments[0]

    # Get code from SVN
    release_dir = export_svn_branch(options.branch)

    # Figure out version if user didn't specify one
    if not options.version:
      rev_str = get_branch_revision(options.branch)
      br_name = options.branch.replace('branches/', '', 1).replace('_', '-')
      options.version = br_name + '-' + rev_str
    print 'Version of app will be', options.version

  #
  # Copy the private_keys.py file into the directory
  #
  
  if not verify_keyfile(release_dir):
    get_keyfile(options.private_key, release_dir)
  if not verify_keyfile(release_dir):
    print 'private_keys.py file did not make it to the frontend directory'
    sys.exit(-1)
  print 'Private keys in place'
  
  #
  # Run appcfg.py to push the code to App Engine
  #
  deploy_message = ''
  push_app(release_dir, app_name, options.version, options.for_real)
  
  if options.for_real:
    # TODO(jblocksom): fix these

    # Self tests are iffy
    # test_ok = run_self_tests(app_name)
    test_ok = True

    # Some Mac OS X update seem broke opening the dashboard
    # if options.open_dashboard:
    #   open_dashboard(app_name)

  else:
    test_ok = True
    deploy_message = '(Test mode, not really)'

  if test_ok:
    print 'App deployed!', deploy_message
    sys.exit(0)
  else:
    print 'Self test error, please verify manually'
    sys.exit(-1)

if __name__ == '__main__':
  main()
