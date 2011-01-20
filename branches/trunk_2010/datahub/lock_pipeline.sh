#!/bin/sh
:

HOMEDIR=/home/footprint/allforgood/datahub
DASHBOARD=/home/footprint/public_html/dashboard

YMD0=`date +%Y%m%d`
FINGERPRINT="pipeline.py -s"
COUNT=`ps -ef | grep "$FINGERPRINT" | grep -v grep | wc -l`

if [ $COUNT -lt 1 ]
then
	# change to our directory
	cd $HOMEDIR
	if [ $? -ne 0 ]
	then
		./notify_michael.sh cd failed
		exit 1
	else
		./notify_michael.sh pipeline started
	fi

	./notify_michael.sh download started 
	./download.sh
	./notify_michael.sh download complete 

	# clear list of duplicated opps
	rm -fr dups; mkdir dups
	if [ $? -ne 0 ]
	then
		./notify_michael.sh mkdir dups failed
		exit 1
	fi

	./pipeline.py -s

	# make list of opps in index but not in feeds
	YMD=`date +%Y%m%d`

	# update the dashboard
	if [ "$YMD" = "$YMD0" ]
	then
		# but only if we haven't lapped
		cp dashboard.ing/* $DASHBOARD
	fi

	./notify_michael.sh pipeline completed
	./upload.sh

else
	echo -n "pipline lapped " ; date
	./notify_michael.sh pipeline lapped
fi
