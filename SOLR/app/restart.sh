#!/bin/sh
:

PID=`ps -ef | grep start.jar | grep -v grep | awk '{print $2}'`
if [ ! "$PID" = "" ]
then
	echo killing $PID
	kill -9 $PID
fi
#exit

cd /home/footprint/allforgood-read-only/SOLR/app
nohup /usr/bin/java -Xmx1024m -Xms1024m -jar start.jar >logs/solr.out 2>&1 &
PID=`ps -ef | grep start.jar | grep -v grep | awk '{print $2}'`
echo -n "pid=$PID "; date
