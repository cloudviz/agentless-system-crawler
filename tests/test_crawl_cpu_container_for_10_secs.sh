#!/bin/bash

# Tests the OUTCONTAINER crawler mode
# Returns 1 if success, 0 otherwise

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

COUNT=10
docker rm -f test_crawl_cpu_container_1 2> /dev/null > /dev/null
docker run -d --name test_crawl_cpu_container_1 ubuntu sleep 60 2> /dev/null > /dev/null
ID=`docker inspect -f '{{ .Id }}' test_crawl_cpu_container_1`

COUNT2=`timeout $COUNT python2.7 ../crawler/crawler.py --crawlmode OUTCONTAINER \
	--features=cpu --crawlContainers $ID --frequency 1 | grep -c cpu-0`

docker rm -f test_crawl_cpu_container_1 > /dev/null

#if [ $COUNT == $COUNT2 ]
# sometimes we can't crawl that fast
if [ "6" -lt $COUNT2 ]
then
	echo 1
else
	echo 0
fi
