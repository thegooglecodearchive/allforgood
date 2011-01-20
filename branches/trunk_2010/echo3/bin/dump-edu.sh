#!/bin/sh

START=1
STEP=200
cd /usr/home/echo3/www/afg/education
trap 'rm -f *.$$' 0 1 2 3 9 15

while [ true ]
do
	RSP=`../bin/api-fetch.php api_key=superman q="category:education -meetup -craigslist" start=$START step=$STEP`
	#echo $RSP; exit

	if [ $? -ne 0 ]
	then
		echo "$0 error"
		exit
	fi

	ITEMS=`echo "$RSP" | head -2 | tail -1`
	OK=`echo $ITEMS | grep "<item>" | wc -l`
	if [ $START -lt 30000 -a $OK -gt 0 ]
	then
		echo "$ITEMS" >> items.xml.$$
		START=`bc <<EBC
$START + $STEP
EBC
`
	else
		# Mon, 30 Aug 2010 19:52:51 +0000
		W=`date +%w`
		case $W in 
			0) WDAY="Sun" ;;
			1) WDAY="Mon" ;;
			2) WDAY="Tue" ;;
			3) WDAY="Wed" ;;
			4) WDAY="Thu" ;;
			5) WDAY="Fri" ;;
			6) WDAY="Sat" ;;
		esac

		M=`date +%m`
		case $M in 
			01) MON="Jan" ;;
			02) MON="Feb" ;;
			03) MON="Mar" ;;
			04) MON="Apr" ;;
			05) MON="May" ;;
			06) MON="Jun" ;;
			07) MON="Jul" ;;
			08) MON="Aug" ;;
			09) MON="Sep" ;;
			10) MON="Oct" ;;
			11) MON="Nov" ;;
			12) MON="Dec" ;;
		esac

		YR=`date +%Y`
		DAY=`date +%d | sed s/^0//`
		HMS=`date +%H:%M:%S`
		LAST_BUILD_DATE="$WDAY, $DAY $MON $YR $HMS +0000"

		cat intro.xml | sed s/LAST_BUILD_DATE/"$LAST_BUILD_DATE"/ > list.xml.$$
		if [ ! -f items.xml.$$ ]
		then
			echo "no items?"
			exit
		fi
		cat items.xml.$$ >> list.xml.$$
		cat outro.xml >> list.xml.$$
		cp list.xml.$$ uncompressed-list.xml
		gzip list.xml.$$
		if [ $? -eq 0 ]
		then
			mv list.xml.$$.gz list.xml.gz
		fi
		exit
	fi
done
