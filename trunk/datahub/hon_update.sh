#!/bin/sh
:
cd /home/footprint/allforgood-read-only/datahub/

FINGERPRINT="pipeline.py -s"
COUNT=`ps -ef | grep "$FINGERPRINT" | grep -v grep | wc -l`
if [ $COUNT -gt 0 ]
then
	exit
fi

date
LOGDEL=""
for DEL in `find ./HONupdates/updateHON*.xml.delete | sort`
do
	LOGDEL=`echo $DEL | sed s/xml/log/`
	date > $LOGDEL

	mv $DEL $DEL.processed >> $LOGDEL 2>&1
	./xmeetup.sh $DEL.processed >> $LOGDEL 2>&1
done

for XML in `find ./HONupdates/updateHON*.xml | sort`
do
	rm -f updateHON1.transformed
	LOG=`echo $XML | sed s/xml/log/`
	ERRLOG=`echo $XML | sed s/xml/err/`
	if [ -s "$LOGDEL" ]
	then
		cat $LOGDEL > $LOG
	fi
	date >> $LOG

	echo "./pipeline.py -s $XML" >> $LOG
	nice ./pipeline.py -s $XML >> $LOG 2>> $ERRLOG
	WHEN=`date +%Y%m%d%H%M%S`
	mv $XML $XML.processed.$WHEN
	if [ -s updateHON1.transformed ]
	then
		mv updateHON1.transformed HONupdates/$WHEN.transformed
		./upload.sh HONupdates/$WHEN.transformed >> $LOG 2>&1
		wget -q -O /dev/null http://staging.servicefootprint.appspot.com/cache-update
	else
		echo "processing error" >> $LOG
	fi
	echo "\nEOF" >> $LOG
done
