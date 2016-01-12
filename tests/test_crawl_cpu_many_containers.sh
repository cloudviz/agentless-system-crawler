#!/bin/bash

# Tests the OUTCONTAINER crawler mode for 32 containers
# Returns 1 if success, 0 otherwise

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

COUNT=4

for i in `seq 1 $COUNT`
do
	docker rm -f test_crawl_cpu_many_containers_$i 2> /dev/null > /dev/null
	docker run -d --name test_crawl_cpu_many_containers_$i ubuntu sleep 60 2> /dev/null > /dev/null
done

IDS=`docker ps | grep test_crawl_cpu_many_containers | awk '{printf "%s,",  $1}' | sed s/,$//g`

COUNT2=`python2.7 ../crawler/crawler.py --crawlmode OUTCONTAINER \
	--features=cpu --crawlContainers $IDS --numprocesses 2 | grep -c cpu-0`

for i in `seq 1 $COUNT`
do
	docker rm -f test_crawl_cpu_many_containers_$i > /dev/null
done

if [ $COUNT == $COUNT2 ]
then
	echo 1
else
	echo 0
fi

