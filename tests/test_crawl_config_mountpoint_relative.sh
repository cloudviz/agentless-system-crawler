#!/bin/bash

# Tests the OUTCONTAINER crawler mode
# Returns 1 if success, 0 otherwise

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

UUID=`uuid`
mkdir -p /etc/etc2
echo $UUID >> /etc/etc2/ric_config

python2.7 ../crawler/crawler.py --crawlmode MOUNTPOINT \
	--features=config --options '{"config": {"known_config_files":["etc2/ric_config"]}}' \
	--mountpoint /etc/ > /tmp/test_crawl_config_mountpoint_relative

COUNT_MSG=`grep $UUID /tmp/test_crawl_config_mountpoint_relative | wc -l`
COUNT_FEATURES=`grep '^config' /tmp/test_crawl_config_mountpoint_relative | wc -l`

# 2 = METADATA + FEATURE
COUNT_TOTAL=`cat /tmp/test_crawl_config_mountpoint_relative | wc -l`

if [ $COUNT_MSG == "1" ] && [ $COUNT_FEATURES == "1" ] && [ $COUNT_TOTAL == "2" ]
then
	echo 1
else
	echo 0
fi

rm -rf /etc/etc2
