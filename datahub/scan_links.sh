#!/bin/sh
:

#OTHER='footprint@li169-139.members.linode.com'
OTHER='footprint@li67-22.members.linode.com'

DIR=/home/footprint/allforgood-read-only/datahub

ALL_TSV=$*
if [ "$ALL_TSV" = "" ]
then
	ALL_TSV=`ls -1 *.transformed`
fi

cd $DIR
if [ ! -d links ]
then
	mkdir links
fi

if [ ! -d bad-links ]
then
	mkdir bad-links
fi

for TSV in $ALL_TSV
do
	if [ -s $TSV ]
	then
		/home/footprint/bin/tsv $TSV detailurl > links/scan.lis.$$
		while read LINK
		do
			./check_links.py $LINK
			sleep 1
		done < links/scan.lis.$$
		rm -f links/scan.lis.$$
	fi
done
