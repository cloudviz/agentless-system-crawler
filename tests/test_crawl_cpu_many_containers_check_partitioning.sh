#!/bin/bash

# Tests the OUTCONTAINER crawler mode for 32 containers
# Returns 1 if success, 0 otherwise

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

COUNT=8
LOG_FILE=/tmp/test_crawl_cpu_many_containers_check_partitioning

rm -f ${LOG_FILE}*

for i in `seq 1 $COUNT`
do
	docker rm -f test_crawl_cpu_many_containers_$i 2> /dev/null > /dev/null
	docker run -d --name test_crawl_cpu_many_containers_$i ubuntu sleep 60 2> /dev/null > /dev/null
done

IDS=`docker ps | grep test_crawl_cpu_many_containers | awk '{printf "%s,",  $1}' | sed s/,$//g`

rm  -f *.log

COUNT2=`python2.7 ../crawler/crawler.py --crawlmode OUTCONTAINER \
	--features=cpu --crawlContainers $IDS --numprocesses 2 \
        --logfile ${LOG_FILE}.log | grep -c cpu-0`

# Check that each crawler process got at least one container assigned to it.
# It would be very VERY unlucky for one of them to get the 8 containers.
COUNT_LOGS_1=`grep -c "Emitted 2 features" ${LOG_FILE}-0.log`
COUNT_LOGS_2=`grep -c "Emitted 2 features" ${LOG_FILE}-1.log`

COUNT_LOGS_TOTAL=$(($COUNT_LOGS_1 + $COUNT_LOGS_2))

for i in `seq 1 $COUNT`
do
	docker rm -f test_crawl_cpu_many_containers_$i > /dev/null
done

if [ $COUNT == $COUNT2 ] && [ $COUNT_LOGS_1 -gt "0" ] && [ $COUNT_LOGS_2 -gt "0" ] && [ $COUNT_LOGS_TOTAL == $COUNT ]
then
	echo 1
else
	echo 0
fi

