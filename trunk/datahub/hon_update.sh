#!/bin/sh
:
cd /home/footprint/allforgood-read-only/datahub/

rm -f updateHON1.transformed #legacy probably useless

fingerprint="pipeline.py -s"

# Counts how many instances of the pipeline are running.
countPS=`ps -ef | grep "$fingerprint" | grep -v grep | wc -l`

if [ $countPS -gt 0 ] #If there are other instances running exit
then
	echo "Exiting because the process is running ..."
	exit
fi

date
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
counter=0

        # Process minifeeds that are in queue

for timeStp in `find ./HONupdates/ -name "updateHON*.xml.delete" -o -name "updateHON*.xml" 2> /dev/null| sort | cut -c24-43 | uniq` #returns all unique minifeeds timestamps
do
	counter=$((counter+1))
	if [ $counter -gt 20 ] #If 20  minifeeds have been processed exit
	then
		echo "Exiting because $counter minifeeds were processed  ..."
		exit
	fi

	startTime=$(date +%s)
	# timeStp=`echo $theFile | cut -c24-43` # get the file timestamp
	fileBase="./HONupdates/updateHON-"$timeStp # set the path and default base filename

	echo "$(date) Processing # $counter : updateHON-$timeStp"

	deleteXML=$fileBase".xml.delete" # set the path and filename of the delete file
	feedXML=$fileBase".xml" # set the path and filename of the xml file
	transTSV=$fileBase"1.transformed" #Create variable with TSV transformed file name : updateHON-<timestamp>1.transformed

	log=$fileBase".log" #Create xml log file updateHON-<timestamp>.log
	logDelete=$fileBase".log.delete" #Create  delete log file updateHON-<timestamp>.log.delete
	errorLog=$fileBase".err" #Create error log file updateHON-<timestamp>.err

	if [ -s "$log" -o -s "$logDelete" ] 
	then
		echo "updateHON-$timeStp it is already been handled."
		continue
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
	fi

	#execute delete in SOLR
	if [ -s "$deleteXML" ] # If delete file exists delete it.
	then

		date > $logDelete
		startTimeP=$(date +%s)
		# process for deletion
		mv $deleteXML $deleteXML.processed >> $logDelete 2>&1 #Rename  delete file to updateHON-<timestamp>.xml.delete.processed

		./xmeetup.sh $deleteXML.processed >> $logDelete 2>&1 #Apply file to SOLR index

	#./notify_michael.sh HON deleted

		endTime=$(date +%s)
		diffTime=$(( $endTime - $startTimeP ))
		echo "It took $diffTime seconds to delete" >> $logDelete

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
	else
		echo "processing error" >> $log
	fi

	echo "\nEOF" >> $log
	#./notify_michael.sh HON added

	endTime=$(date +%s)
	diffTime=$(( $endTime - $startTime ))
	echo "It took $diffTime seconds to process minifeed $timeStp " >> $log


done

