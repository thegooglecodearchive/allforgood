#!/bin/sh
:
exit
PATH=/home/footprint/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
#OTHER='footprint@li169-139.members.linode.com'
OTHER='footprint@li67-22.members.linode.com'
EXPORT=1

REMAINING=`ps ax | grep scan_links.sh | grep -v grep | wc -l`
if [ $REMAINING -gt 0 ]
then
	./notify_michael.sh link scan lapped
	exit
fi

# 45 minutes from now
STOP_AT=`./stopwatch.py start 2700`

./notify_michael.sh starting link scan

cd /home/footprint/allforgood-read-only/datahub
if [ $? -ne 0 ]
then
	./notify_michael.sh link scan configuration error
	exit 
fi

if [ $EXPORT -eq 0 ]
then
	for SUBDIR in links bad-links
	do
		rm -fr $SUBDIR ; mkdir $SUBDIR
	done
fi

for TSV in `ls -1 current/*.transformed 2>/dev/null`
do
	echo $TSV
	LOG=`echo $TSV | sed s!/!!g | sed s!current!!g`
	nohup nice ./scan_links.sh $TSV > links/log.$LOG 2>&1 &
done

while [ true ]
do
	REMAINING=`ps aux | grep scan_links.sh | grep -v grep | wc -l`
	if [ $REMAINING -gt 0 ]
	then
		echo $REMAINING feeds remaining
	else
		if [ $EXPORT -ne 0 ]
		then
			for SUBDIR in links bad-links
			do
				ssh $OTHER rm -fr `pwd`/$SUBDIR
				scp -qr $SUBDIR $OTHER:`pwd`
			done
		fi

		./notify_michael.sh link scan complete
		break
	fi

	STOP_NOW=`./stopwatch.py stop $STOP_AT`
	if [ "$STOP_NOW" != "0" ]
	then
		./notify_michael.sh link scan timed out
		break
	fi

	./stopwatch.py sleep 60
done
