#!/bin/bash

# Tests the MOUNTPOINT crawler mode
# Returns 1 if success, 0 otherwise

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

python2.7 ../../crawler/crawler.py --crawlmode MOUNTPOINT --features package,disk \
	--mountpoint '/' > /tmp/test_crawl_packages_disks_mountpoint

COUNT_PACKAGE=`grep '^package' /tmp/test_crawl_packages_disks_mountpoint | wc -l`
COUNT_DISK=`grep '^disk' /tmp/test_crawl_packages_disks_mountpoint | wc -l`

if [ $COUNT_PACKAGE -gt "10" ] && [ $COUNT_DISK -gt "0" ]
then
	echo 1
else
	echo 0
fi
