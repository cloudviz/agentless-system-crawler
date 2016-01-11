#!/bin/bash

# Tests the OUTCONTAINER crawler mode
# Returns 1 if success, 0 otherwise

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

echo ble >> /etc/ric_config
mkdir -p /root/bla
echo bla >> /root/bla/ble

docker rm -f test_crawl_cpu_container_1 2> /dev/null > /dev/null
docker run -d --name test_crawl_cpu_container_1 ubuntu bash -c "echo bla >> /etc/ric_config; mkdir -p /bla; echo bla >> /bla/ble; sleep 60" 2> /dev/null > /dev/null
ID=`docker inspect -f '{{ .Id }}' test_crawl_cpu_container_1`

rm -f /tmp/test_crawl_all_features_container*
rm -f /tmp/test_crawl_all_features_invm*

# start teh container crawler
python2.7 ../crawler/crawler.py --crawlmode OUTCONTAINER --numprocesses 2 \
	--features=cpu,memory,os,config,file,package,dockerinspect,dockerhistory,metric,load --crawlContainers $ID \
	--url file:///tmp/test_crawl_all_features_container --frequency 1 --logfile crawler-container.log --options \
	'{"config": {"known_config_files":["etc/ric_config"]}, "file": {"root_dir": "/bla/"}}' &
PID_CONTAINER=$!

# start teh VM crawler
python2.7 ../crawler/crawler.py \
	--features=cpu,memory,os,config,file,package,dockerps,metric,load --numprocesses 1 \
	--url file:///tmp/test_crawl_all_features_invm --frequency 1 --logfile crawler-vm.log --options \
	'{"config": {"known_config_files":["etc/ric_config"]}, "file": {"root_dir": "/root/bla/"}}' &
PID_VM=$!

sleep 10

COUNT_CONTAINER_1=`grep  ^cpu /tmp/test_crawl_all_features_container* | wc -l`
COUNT_CONTAINER_2=`grep  ^memory /tmp/test_crawl_all_features_container* | wc -l`
COUNT_CONTAINER_3=`grep  ^os /tmp/test_crawl_all_features_container* | wc -l`
COUNT_CONTAINER_4=`grep  ^config /tmp/test_crawl_all_features_container* | wc -l`
COUNT_CONTAINER_5=`grep  ^file /tmp/test_crawl_all_features_container* | wc -l`
COUNT_CONTAINER_6=`grep  ^package /tmp/test_crawl_all_features_container* | wc -l`
COUNT_CONTAINER_7=`grep  ^dockerinspect /tmp/test_crawl_all_features_container* | wc -l`
COUNT_CONTAINER_8=`grep  ^dockerhistory /tmp/test_crawl_all_features_container* | wc -l`
COUNT_CONTAINER_9=`grep  ^metric /tmp/test_crawl_all_features_container* | wc -l`
COUNT_CONTAINER_10=`grep  ^load /tmp/test_crawl_all_features_container* | wc -l`

COUNT_VM_1=`grep  ^cpu /tmp/test_crawl_all_features_invm* | wc -l`
COUNT_VM_2=`grep  ^memory /tmp/test_crawl_all_features_invm* | wc -l`
COUNT_VM_3=`grep  ^os /tmp/test_crawl_all_features_invm* | wc -l`
COUNT_VM_4=`grep  ^config /tmp/test_crawl_all_features_invm* | wc -l`
COUNT_VM_5=`grep  ^file /tmp/test_crawl_all_features_invm* | wc -l`
COUNT_VM_6=`grep  ^package /tmp/test_crawl_all_features_invm* | wc -l`
COUNT_VM_7=`grep  ^dockerps /tmp/test_crawl_all_features_invm* | wc -l`
COUNT_VM_8=`grep  ^metric /tmp/test_crawl_all_features_invm* | wc -l`
COUNT_VM_9=`grep  ^load /tmp/test_crawl_all_features_invm* | wc -l`


if [ $COUNT_CONTAINER_1 -gt "2" ] && \
	[ $COUNT_CONTAINER_2 -gt "2" ] && \
	[ $COUNT_CONTAINER_3 -gt "2" ] && \
	[ $COUNT_CONTAINER_4 -gt "2" ] && \
	[ $COUNT_CONTAINER_5 -gt "2" ] && \
	[ $COUNT_CONTAINER_6 -gt "2" ] && \
	[ $COUNT_CONTAINER_7 -gt "2" ] && \
	[ $COUNT_CONTAINER_8 -gt "2" ] && \
	[ $COUNT_CONTAINER_9 -gt "2" ] && \
	[ $COUNT_CONTAINER_10 -gt "2" ] && \
	[ $COUNT_VM_1 -gt "2" ] && \
	[ $COUNT_VM_2 -gt "2" ] && \
	[ $COUNT_VM_3 -gt "2" ] && \
	[ $COUNT_VM_4 -gt "2" ] && \
	[ $COUNT_VM_5 -gt "2" ] && \
	[ $COUNT_VM_6 -gt "2" ] && \
	[ $COUNT_VM_7 -gt "2" ] && \
	[ $COUNT_VM_8 -gt "2" ] && \
	[ $COUNT_VM_9 -gt "2" ]
then
	echo 1
else
	echo 0
fi

exec 2> /dev/null
kill -9 $PID_CONTAINER
kill -9 $PID_VM

rm -f /tmp/test_crawl_all_features_container*
rm -f /tmp/test_crawl_all_features_invm*
rm -rf /root/bla
rm -f /etc/ric_config

docker rm -f test_crawl_cpu_container_1 > /dev/null
