#!/bin/sh
:

# pointsoflight 224382700
# HandsOnNetwork 15728184
# createthegood 17999296
# servedotgov 59204932
# live_united 16506355
# idealist 15096075
# Habitat_org 33898911
# BetheChangeInc 11379362
# UniversalGiving 17009647
# pamelahawley 15591578
# communitysvc 121839819
# huffpostimpact 80681990
# causecast 14090017
# All_for_Good 34344129

if [ ! -d /home/footprint/public_html/twitter ]
then
	mkdir /home/footprint/public_html/twitter
fi
cd /home/footprint/public_html/twitter

for FEED in 224382700 15728184 17999296 59204932 16506355 15096075 33898911 11379362 17009647 15591578 121839819 80681990 14090017 34344129 
do
	wget -q -O $FEED.rss "http://twitter.com/statuses/user_timeline/$FEED.rss"
done
