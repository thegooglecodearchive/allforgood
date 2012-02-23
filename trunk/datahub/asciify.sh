#!/bin/sh
:

if [ $# -gt 0 ]
then
	FILES=$*
else
	FILES=`ls -1 *.xml`
fi

for FILE in $FILES
do
	./utf8.py < $FILE > xml.$$
	if [ $? -eq 0 ]
	then
		mv xml.$$ $FILE
	fi
done
