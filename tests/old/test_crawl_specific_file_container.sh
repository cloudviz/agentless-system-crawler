#!/bin/bash

# Tests the OUTCONTAINER crawler mode
# Returns 1 if success, 0 otherwise

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

docker rm -f test_crawl_file_container_1 2> /dev/null > /dev/null
docker run -d --name test_crawl_file_container_1 ubuntu bash -c "mkdir /bla; echo test > /bla/ble; sleep 60" 2> /dev/null > /dev/null
ID=`docker inspect -f '{{ .Id }}' test_crawl_file_container_1`

python2.7 ../../crawler/crawler.py --crawlmode OUTCONTAINER \
	--features=file --crawlContainers $ID --options \
	'{"config": {"known_config_files":["etc/test.test"]}, "file": {"root_dir": "/bla/"}}' > \
	/tmp/test_crawl_config_container

# 2 as there is one feature for /bla and one for /bla/ble
COUNT_MSG=`grep "/bla" /tmp/test_crawl_config_container | wc -l`

# 2 as there is one feature for /bla and one for /bla/ble
COUNT_FEATURES=`grep '^file' /tmp/test_crawl_config_container | wc -l`

# 3 = metadata and 2 features
COUNT_TOTAL=`cat /tmp/test_crawl_config_container | wc -l`

if [ $COUNT_MSG == "2" ] && [ $COUNT_FEATURES == "2" ] && [ $COUNT_TOTAL == "3" ]
then
	echo 1
else
	echo 0
fi

docker rm -f test_crawl_file_container_1 > /dev/null
