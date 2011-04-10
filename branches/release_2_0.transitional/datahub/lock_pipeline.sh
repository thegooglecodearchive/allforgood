#!/bin/sh
:
#set -x

DIR=/home/footprint/allforgood-read-only/datahub
DASHBOARD_DIR=/home/footprint/public_html/dashboard

YMD0=`date +%Y%m%d`
FINGERPRINT="pipeline.py -s"
COUNT=`ps -ef | grep "$FINGERPRINT" | grep -v grep | wc -l`

if [ $COUNT -lt 1 ]
then
	# change to our directory
	cd $DIR
	if [ $? -ne 0 ]
	then
		./notify_michael.sh cd failed
		exit 1
	else
		./notify_michael.sh pipeline started
	fi

	if [ "$*" = "" ]
	then
		./notify_michael.sh download started 
		./download.sh
		./notify_michael.sh download complete 
	fi

	# clear list of duplicated opps
	rm -fr dups; mkdir dups
	if [ $? -ne 0 ]
	then
		./notify_michael.sh mkdir dups failed
		exit 1
	fi

	./notify_michael.sh pipeline processing
	./pipeline.py -s $*

        if [ $? -ne 0 ]
        then
                ./notify_michael.sh pipeline FAIL
                exit 1
        fi

        # upload the opps to solr
	./notify_michael.sh pipeline uploading
	if [ "$*" = "" ]
	then
		# evaluate processing results before uploading
                for FILE in `ls -1 *.transformed`
                do
                        NAME=`basename $FILE`
                        CFILE="current/$NAME"
                        if [ ! -s $CFILE ]  
                        then
                                cp $FILE $CFILE
                        else
                                NEWSZ=`stat -c %s $FILE`
                                OLDSZ=`stat -c %s $CFILE`
                                RATIO=`echo "100 * $NEWSZ / $OLDSZ" | bc`
                                if [ $RATIO -lt 70 ]
                                then
                                        ./notify_team.sh manually check $FILE
                                else
                                        cp $FILE $CFILE
                                fi
                        fi
                done

		./upload.sh
	else
		for IT in $*
		do
        		./upload.sh `ls -1 $IT*.transformed`
		done
	fi
	./notify_michael.sh pipeline upload complete

        # update the dash board
        YMD=`date +%Y%m%d`
        if [ "$YMD" = "$YMD0" -a "$*" = "" ]
        then
                # but only if we haven't lapped
                cp dashboard.ing/* $DASHBOARD_DIR
        fi

	./notify_michael.sh pipeline stopped
else
	echo -n "pipline lapped " ; date
	./notify_michael.sh pipeline lapped
fi