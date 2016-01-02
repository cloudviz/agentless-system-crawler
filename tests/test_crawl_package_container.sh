#!/bin/bash

# Tests the OUTCONTAINER crawler mode
# Returns 1 if success, 0 otherwise

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

docker rm -f test_crawl_package_container_1 2> /dev/null > /dev/null
docker run -d --name test_crawl_package_container_1 ubuntu sleep 60 2> /dev/null > /dev/null
ID=`docker inspect -f '{{ .Id }}' test_crawl_package_container_1`


COUNT=`python2.7 ../crawler/crawler.py --crawlmode OUTCONTAINER \
	--features=package --crawlContainers $ID | grep ^package | grep -c ubuntu`

docker rm -f test_crawl_package_container_1 > /dev/null

# Should have at least 10 packages
if [ $COUNT -gt "10" ]
then
	echo 1
else
	echo 0
fi
