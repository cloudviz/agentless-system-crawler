#!/bin/bash

# Tests the OUTCONTAINER crawler mode
# Returns 1 if success, 0 otherwise

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

docker rm -f test_crawl_cpu_container_1 2> /dev/null > /dev/null
docker run -d --name test_crawl_cpu_container_1 ubuntu bash -c "echo bla >> /etc/ric_config; mkdir -p /bla; echo bla >> /bla/ble; sleep 60" 2> /dev/null > /dev/null
ID=`docker inspect -f '{{ .Id }}' test_crawl_cpu_container_1`

rm -f /tmp/test_crawl_all_features_container*

python2.7 ../config_and_metrics_crawler/crawler.py --crawlmode OUTCONTAINER \
	--features=cpu,memory,os,config,file,package,dockerinspect,dockerhistory,metric,load --crawlContainers $ID \
	--url file:///tmp/test_crawl_all_features_container --options \
	'{"config": {"known_config_files":["etc/ric_config"]}, "file": {"root_dir": "/bla/"}}'

COUNT_1=`grep  ^cpu /tmp/test_crawl_all_features_container* | wc -l`
COUNT_2=`grep  ^memory /tmp/test_crawl_all_features_container* | wc -l`
COUNT_3=`grep  ^os /tmp/test_crawl_all_features_container* | wc -l`

# This sholuld be just and exactly 1, as ther eis only /etc/ric_config
COUNT_4=`grep  ^config /tmp/test_crawl_all_features_container* | wc -l`

# This should be just and exactly 2, as there is only /bla and /bla/ble
COUNT_5=`grep  ^file /tmp/test_crawl_all_features_container* | wc -l`
COUNT_6=`grep  ^package /tmp/test_crawl_all_features_container* | wc -l`
COUNT_7=`grep  ^dockerinspect /tmp/test_crawl_all_features_container* | wc -l`
COUNT_8=`grep  ^dockerhistory /tmp/test_crawl_all_features_container* | wc -l`
COUNT_9=`grep  ^metric /tmp/test_crawl_all_features_container* | wc -l`
COUNT_10=`grep  ^load /tmp/test_crawl_all_features_container* | wc -l`

if [ $COUNT_1 -gt "0" ] && \
	[ $COUNT_2 -eq "1" ] && \
	[ $COUNT_3 -eq "1" ] && \
	[ $COUNT_4 -eq "1" ] && \
	[ $COUNT_5 -eq "2" ] && \
	[ $COUNT_6 -gt "0" ] && \
	[ $COUNT_7 -eq "1" ] && \
	[ $COUNT_8 -gt "0" ] && \
	[ $COUNT_9 -gt "0" ] && \
	[ $COUNT_10 -eq "1" ]
then
	echo 1
else
	echo 0
fi

docker rm -f test_crawl_cpu_container_1 > /dev/null
rm -f /tmp/test_crawl_all_features_container*
