#!/bin/bash

# Tests the MOUNTPOINT crawler mode
# Returns 1 if success, 0 otherwise

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi


python2.7 ../crawler/crawler.py --crawlmode MOUNTPOINT --features file,config \
	--mountpoint '/etc/' > /tmp/test_crawl_config_packages_mountpoint

COUNT_CONFIG=`grep '^config' /tmp/test_crawl_config_packages_mountpoint | wc -l`
COUNT_FILES=`grep '^file' /tmp/test_crawl_config_packages_mountpoint | wc -l`

if [ $COUNT_CONFIG -gt "0" ] && [ $COUNT_FILES -gt "10" ]
then
	echo 1
else
	echo 0
fi
