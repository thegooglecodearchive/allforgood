#!/bin/sh
:
cd /home/footprint/allforgood-read-only/datahub/

maxThreads=10

isScriptRunning=`ps -ef | grep "mthread_hon_update.sh" | grep -v grep | wc -l`
if [ $isScriptRunning -gt 3 ] 
then
	echo "Exiting because $isScriptRunning instance of $0 is already running ..."
	ps -ef | grep "mthread_hon_update.sh" | grep -v grep 
	exit
fi

date

while [ true ]
do
        # Process any minifeeds that are in queue
	for timeStp in `find ./HONupdates/ -name "updateHON*.xml.delete" -o -name "updateHON*.xml" 2> /dev/null| sort | cut -c24-43 | uniq` #returns all unique minifeeds
	do
		# scheduled cron to create pause.minifeeds when footprint.xml is ready
		if [ -f pause.minifeeds ]
		then
			break
		fi

		# if lock_pipeline is running, just wait
		havePipeline=`ps -ef | grep "lock_pipeline.sh" | grep -v grep | wc -l`
		if [ $havePipeline -gt 1 ]
		then
			break
		fi

		# if we have max threads running, just wait
		threadCount=`ps -ef | grep "hon_update_thread.sh" | grep -v grep | wc -l`
		if [ $threadCount -ge $maxThreads ]
		then
			break
		fi

		# skip this feed if it has already been processed 
		fileBase="./HONupdates/updateHON-"$timeStp
		log=$fileBase".log"
		logDelete=$fileBase".log.delete"
        if [ -s "$log" -o -s "$logDelete" ]
		then
			continue
		fi

		# if we dont have a thread for this one start it now
		haveThread=`ps -ef | grep "hon_update_thread.sh $timeStp" | grep -v grep | wc -l`
		if [ $haveThread -lt 1 ]
		then
				./hon_update_thread.sh $timeStp &
		fi
	done
	sleep 5
done

