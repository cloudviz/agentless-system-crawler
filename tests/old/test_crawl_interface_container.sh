#!/bin/bash

# Tests the OUTCONTAINER crawler mode
# Returns 1 if success, 0 otherwise

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

docker rm -f test_crawl_interface_container_1 2> /dev/null > /dev/null
docker run -d --name test_crawl_interface_container_1 ubuntu sleep 60 2> /dev/null > /dev/null
ID=`docker inspect -f '{{ .Id }}' test_crawl_interface_container_1`

python2.7 ../../crawler/crawler.py --crawlmode OUTCONTAINER \
	--features=interface --crawlContainers $ID | grep -c eth0

docker rm -f test_crawl_interface_container_1 > /dev/null
