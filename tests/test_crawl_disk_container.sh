#!/bin/bash

# Tests the OUTCONTAINER crawler mode
# Returns 1 if success, 0 otherwise

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

docker rm -f test_crawl_file_container_1 2> /dev/null > /dev/null
docker run -d --name test_crawl_file_container_1 ubuntu bash -c "echo test > /etc/test.test; sleep 60" 2> /dev/null > /dev/null
ID=`docker inspect -f '{{ .Id }}' test_crawl_file_container_1`

# pretty much only docker contianers mount a /etc/resolv.conf partition
python2.7 ../config_and_metrics_crawler/crawler.py --crawlmode OUTCONTAINER \
	--features=disk --crawlContainers $ID | grep -c "/etc/resolv.conf"

docker rm -f test_crawl_file_container_1 > /dev/null
