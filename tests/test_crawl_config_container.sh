#!/bin/bash

# Tests the OUTCONTAINER crawler mode
# Returns 1 if success, 0 otherwise

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

docker rm -f test_crawl_config_container_1 2> /dev/null > /dev/null
UUID=`uuid`
docker run -d --name test_crawl_config_container_1 ubuntu bash -c "echo $UUID > /etc/ric_config; sleep 60" 2> /dev/null > /dev/null
ID=`docker inspect -f '{{ .Id }}' test_crawl_config_container_1`

rm -f /tmp/test_crawl_config_container

python2.7 ../crawler/crawler.py --crawlmode OUTCONTAINER \
	--features=config --crawlContainers $ID --options '{"config": {"known_config_files":["etc/ric_config"]}}' \
	> /tmp/test_crawl_config_container

COUNT_MSG=`grep $UUID /tmp/test_crawl_config_container | wc -l`
COUNT_FEATURES=`grep '^config' /tmp/test_crawl_config_container | wc -l`

# 2 = METADATA + FEATURE
COUNT_TOTAL=`cat /tmp/test_crawl_config_container | wc -l`

if [ $COUNT_MSG == "1" ] && [ $COUNT_FEATURES == "1" ] && [ $COUNT_TOTAL == "2" ]
then
	echo 1
else
	echo 0
fi
docker rm -f test_crawl_config_container_1 > /dev/null
