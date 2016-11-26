#!/bin/bash

# Tests the OUTCONTAINER crawler mode
# Returns 1 if success, 0 otherwise

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

# start a container for dockerps to return something
docker rm -f test_crawl_all_features_invm 2> /dev/null > /dev/null
docker run -d --name test_crawl_all_features_invm ubuntu bash -c "echo bla >> /etc/ric_config; mkdir -p /bla; echo bla >> /bla/ble; sleep 60" 2> /dev/null > /dev/null

echo ble >> /etc/ric_config
mkdir -p /root/bla
echo bla >> /root/bla/ble

timeout 10 python2.7 ../../crawler/crawler.py \
	--features=cpu,memory,os,config,file,package,dockerps,metric,load \
	--url file:///tmp/test_crawl_all_features_invm --frequency 1 --options \
	'{"config": {"known_config_files":["etc/ric_config"]}, "file": {"root_dir": "/root/bla/"}}'

COUNT_1=`grep  ^cpu /tmp/test_crawl_all_features_invm* | wc -l`
COUNT_2=`grep  ^memory /tmp/test_crawl_all_features_invm* | wc -l`
COUNT_3=`grep  ^os /tmp/test_crawl_all_features_invm* | wc -l`
COUNT_4=`grep  ^config /tmp/test_crawl_all_features_invm* | wc -l`
COUNT_5=`grep  ^file /tmp/test_crawl_all_features_invm* | wc -l`
COUNT_6=`grep  ^package /tmp/test_crawl_all_features_invm* | wc -l`
COUNT_7=`grep  ^dockerps /tmp/test_crawl_all_features_invm* | wc -l`
COUNT_8=`grep  ^metric /tmp/test_crawl_all_features_invm* | wc -l`
COUNT_9=`grep  ^load /tmp/test_crawl_all_features_invm* | wc -l`

if [ $COUNT_1 -gt "1" ] && \
	[ $COUNT_2 -gt "1" ] && \
	[ $COUNT_3 -gt "1" ] && \
	[ $COUNT_4 -gt "1" ] && \
	[ $COUNT_5 -gt "1" ] && \
	[ $COUNT_6 -gt "1" ] && \
	[ $COUNT_7 -gt "1" ] && \
	[ $COUNT_8 -gt "1" ] && \
	[ $COUNT_9 -gt "1" ]
then
	echo 1
else
	echo 0
fi

docker rm -f test_crawl_all_features_invm 2> /dev/null > /dev/null
rm -f /tmp/test_crawl_all_features_invm*
rm -rf /root/bla
rm -f /etc/ric_config
