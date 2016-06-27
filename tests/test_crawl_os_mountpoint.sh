#!/bin/bash

# Tests the OUTCONTAINER crawler mode
# Returns 1 if success, 0 otherwise

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

python2.7 ../config_and_metrics_crawler/crawler.py --crawlmode MOUNTPOINT \
	--features=os \
	--mountpoint / 	> /tmp/test_crawl_config_mountpoint

COUNT_FEATURES=`grep '^os' /tmp/test_crawl_config_mountpoint | wc -l`

# 2 = METADATA + FEATURE
COUNT_TOTAL=`cat /tmp/test_crawl_config_mountpoint | wc -l`

if [ $COUNT_FEATURES == "1" ] && [ $COUNT_TOTAL == "2" ]
then
	echo 1
else
	echo 0
fi

