#!/bin/bash

# Tests the OUTCONTAINER crawler mode
# Returns 1 if success, 0 otherwise

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

COUNT=`python2.7 ../config_and_metrics_crawler/crawler.py --crawlmode INVM \
	--features=package |  grep -c ^package`

if [ $COUNT -gt "500" ]
then
	echo 1
else
	echo 0
fi
