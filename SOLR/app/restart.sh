#!/bin/sh
:

while [ true ]
do
	PID=`ps -ef | grep start.jar | grep -v grep | awk '{print $2}' | head -1`
	if [ "$PID" = "" ]
	then
		break
	else
		echo killing $PID
		kill -9 $PID
	fi
done
#exit

cd /home/footprint/allforgood-read-only/SOLR/3app
nohup /usr/bin/java -Xmx1024m -Xms1024m -jar start.jar >logs/solr.out 2>&1 &
PID=`ps -ef | grep start.jar | grep -v grep | awk '{print $2}'`
echo -n "pid=$PID "; date
