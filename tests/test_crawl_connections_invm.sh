#!/bin/bash

# Tests the OUTCONTAINER crawler mode
# Returns 1 if success, 0 otherwise

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

COUNT=`python2.7 ../crawler/crawler.py --crawlmode INVM \
	--features=connection | grep -c ^connection`

# Any VM should have at least a pair of connections
if [ $COUNT -gt "2" ]
then
	echo 1
else
	echo 0
fi
