#!/bin/bash

# Tests the OUTCONTAINER crawler mode
# Returns 1 if success, 0 otherwise

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

nc -l -p 7777 2> /dev/null > /dev/null &
PID=$!

COUNT=`python2.7 ../config_and_metrics_crawler/crawler.py --crawlmode INVM \
	--features=connection | grep -c ^connection`

# Any VM should have at least a pair of connections
if [ $COUNT -gt "0" ]
then
	echo 1
else
	echo 0
fi

# Just avoid having the "Terminated ..." error showing up
exec 2> /dev/null
kill -9 $PID > /dev/null 2> /dev/null
