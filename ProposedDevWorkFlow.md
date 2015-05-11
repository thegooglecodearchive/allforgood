## WorkFlow Chart ##

Below is the proposed workflow for getting code from the developers, to QA, and eventually production.

  1. Design Accepted - The basic requirements for the feature or bug have been discussed and understood by both the developer and 'owner'.  More details on this below.
  1. Code Locally - The developer uses the GettingStarted guide to setup a local all For Good development environment, and makes the changes to his or her local instance.
  1. Upload to Dev GAE Instance - Each developer will have his or her own development instance hosted on appspot.com. (e.g. allforgood-dev-ryans.appspot.com).  To share changes with other AfG contributors, devs should upload to their personal instance (see CommonGotchas for some issues we should work out to make this easier).
  1. Code Review - As explained in the GettingStarted page, the code then goes through a series of code reviews, where they developer explains his or her changes, and provides publically accessible before and after URLs.
  1. If the Code Review is not approved, the developer goes back to making local changes and the process repeats.
  1. Once the code review is approved, the developer commits his or her changes to SVN.
  1. The developer then pushes the latest copy of trunk to a QA instance.  This can either be a common QA instance, or one the developer sets up.
  1. QA is notified that the QA instance has been updated with the latest version of trunk.  Ideally, we develop a method for automating or at the very least scripting this process.
  1. QA performs their testing.
  1. QA decides whether or not to accept or reject the changes.
  1. If QA does not accept the changes, they provide a bug report with the reasons for not accepting the build, and the workflow is reset to the appropriate step (e.g. #2 if new development work is required).
  1. If QA Accepts the changes, then the decision whether or not to push the changes to production needs to be made.  See below for more details.
    1. If the changes are pushed to production, they are deployed shortly.
    1. If they are not deployed, they remain in SVN until the next iteration of the development process.

## Design Accepted, before dev work starts ##

The above workflow assumes that design has been accepted before we begin.  What does that mean?

For bugs, it means that the exact issue is well defined, and that the required outcome is well understood.  For example, if the bug is "Display of dates should be more human readable" then suggested date formats for all possible combinations should be worked out and approved before coding starts.

For feature requests, the level of definition varies in proportion to the impact of the feature.  Small changes can get by with a basic description and possibly a mock-up.  Larger features with wide-ranging impact must be more defined, and the UI, architectural changes, and testing plans should be well defined before development cycles are committed.

## Personal Instances ##

The nice thing about App Engine is that it's very easy for each developer to have one or more publicly available 'personal' instances.  So, rather than contend for a single QA instance, it makes more sense for each developer or development group to maintain their own app engine instances for dev and QA.  However, we need to figure out the best way to share SOLR instances.  This document is geared towards front-end development, changes to the back-end SOLR system will need a more complicated work-flow unless the developer can set-up their own private SOLR instance.