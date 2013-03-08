#!/bin/sh
:
cd /home/footprint/allforgood-read-only/datahub/

fileBase=""
logDelete=""
log=""
errorLog=""
timeStp=""
transTSV=""
deleteXML=""
feedXML=""
whenStamp=""
startTime=$(date +%s)
startTimeP=$(date +%s)
endTime=$(date +%s)
diffTime=0
timeStp=$1

if [ "$timeStp" = "" ]
then
	echo "usage: $0 timeStp from mthread_hon_update.sh"
	exit 
else
        # Process the given minifeed

	startTime=$(date +%s)
	fileBase="./HONupdates/updateHON-"$timeStp # set the path and default base filename

	echo "$timeStp $(date): Processing updateHON-$timeStp"

	deleteXML=$fileBase".xml.delete" # set the path and filename of the delete file
	feedXML=$fileBase".xml" # set the path and filename of the xml file
	transTSV=$fileBase"1.transformed" #Create variable with TSV transformed file name : updateHON-<timestamp>1.transformed

	log=$fileBase".log" #Create xml log file updateHON-<timestamp>.log
	logDelete=$fileBase".log.delete" #Create  delete log file updateHON-<timestamp>.log.delete
	errorLog=$fileBase".err" #Create error log file updateHON-<timestamp>.err

	if [ -s "$log" -o -s "$logDelete" ] 
	then
		echo "$timeStp $(date): updateHON-$timeStp it is already been handled."
		exit
	fi

	whenStamp=`date +%Y%m%d%H%M%S`

	# Process xml to convert it in a TSV file

	if [ -s "$feedXML" ] # If xml file exists create TSV file.
	then
		date > $log
		startTimeP=$(date +%s)
		echo "./pipeline.py -s $feedXML" >> $log
		nice ./pipeline.py -s $feedXML >> $log 2>> $errorLog # Process tsv file.
		mv $feedXML $feedXML.processed.$whenStamp
		endTime=$(date +%s)
		diffTime=$(( $endTime - $startTimeP ))
		echo "It took $diffTime seconds to create TSV" >> $log
		TSV_SZ=0
		if [ -f $transTSV ]
		then
			TSV_SZ=`stat -c %s $transTSV`
		fi
		echo "$timeStp $(date): It took $diffTime seconds to create TSV $TSV_SZ bytes"
	fi

	#execute delete in SOLR
	if [ -s "$deleteXML" ] # If delete file exists delete it.
	then

		date > $logDelete
		startTimeP=$(date +%s)
		# process for deletion
		mv $deleteXML $deleteXML.processed >> $logDelete 2>&1 #Rename  delete file to updateHON-<timestamp>.xml.delete.processed

		./xmeetup.sh $deleteXML.processed >> $logDelete 2>&1 #Apply file to SOLR index

		endTime=$(date +%s)
		diffTime=$(( $endTime - $startTimeP ))
		echo "It took $diffTime seconds to delete" >> $logDelete
		echo "$timeStp $(date): It took $diffTime seconds to delete"

	fi

	if [ -s "$logDelete" ] # If log.delete file exists append it to the xml log file.
	then
		cat $logDelete >> $log
	fi

	#execute insert in SOLR
	if [ -s "$transTSV" ] #Test if TSV file exists
	then
		startTimeP=$(date +%s)
		rm -f $fileBase"1"
		rm -f $fileBase"1.gz"
		mv $transTSV $fileBase.$whenStamp.transformed
		./upload.sh $fileBase.$whenStamp.transformed >> $log 2>&1
		# wget -q -O /dev/null http://staging.servicefootprint.appspot.com/cache-update
		# echo "processed $feedXML"
		endTime=$(date +%s)
		diffTime=$(( $endTime - $startTimeP ))
		echo "It took $diffTime seconds to insert" >> $log
		echo "$timeStp $(date): It took $diffTime seconds to insert"
	else
		echo "processing error" >> $log
		echo "$timeStp $(date): processing error"
	fi


	endTime=$(date +%s)
	diffTime=$(( $endTime - $startTime ))
	echo "It took $diffTime seconds to process minifeed $timeStp " >> $log
	echo "\nEOF" >> $log
	echo "$timeStp $(date): It took $diffTime seconds to process minifeed $timeStp "
fi

