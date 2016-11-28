#!/bin/bash

# Tests the INVM crawler mode
# Returns 1 if success, 0 otherwise

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

NUM_CORES=`grep ^processor /proc/cpuinfo | wc -l`


CRAWLED_NUM_CORES=`python2.7 ../../crawler/crawler.py --crawlmode INVM \
	--features=cpu | grep -c cpu-`

if [ $NUM_CORES == $CRAWLED_NUM_CORES ]
then
	echo 1
else
	echo 0
fi
