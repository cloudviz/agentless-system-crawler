#!/bin/bash

# Tests the OUTCONTAINER crawler mode by starting 4 continers, and specifying
# crawl just for 2 of them.
#
# Returns 1 if success, 0 otherwise

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

COUNT=4
ITERS=10

for i in `seq 1 $COUNT`
do
	docker rm -f cpu_many_containers_for_10_secs_check_user_list_$i 2> /dev/null > /dev/null
	docker run -d --name cpu_many_containers_for_10_secs_check_user_list_$i ubuntu sleep 60 2> /dev/null > /dev/null
done

# get docker IDs just for the first 2 containers
ID1=`docker inspect -f '{{ .Id }}' cpu_many_containers_for_10_secs_check_user_list_1`
ID2=`docker inspect -f '{{ .Id }}' cpu_many_containers_for_10_secs_check_user_list_2`

timeout $ITERS python2.7 ../../crawler/crawler.py --crawlmode OUTCONTAINER \
	--features=cpu --crawlContainers ${ID1},${ID2} --numprocesses 2 \
	--frequency 1 --url file:///tmp/cpu_many_containers_for_10_secs_check_user_list

cat /tmp/cpu_many_containers_for_10_secs_check_user_list* > /tmp/cpu_many_containers_for_10_secs_check_user_list_all
COUNT_METADATA_1=`grep -c cpu_many_containers_for_10_secs_check_user_list_1 /tmp/cpu_many_containers_for_10_secs_check_user_list_all`
COUNT_METADATA_2=`grep -c cpu_many_containers_for_10_secs_check_user_list_2 /tmp/cpu_many_containers_for_10_secs_check_user_list_all`

COUNT_CPU=`grep -c cpu-0 /tmp/cpu_many_containers_for_10_secs_check_user_list_all`

for i in `seq 1 $COUNT`
do
	docker rm -f cpu_many_containers_for_10_secs_check_user_list_$i > /dev/null
done

# 2 contianers for 10 seconds (but let's make it 8)
# and metadata for 8 frames for container 1
# and metadata for 8 frames for container 2
if [ $((2 * 8)) -lt $COUNT_CPU ] && [ "8" -lt $COUNT_METADATA_1 ] && [ "8" -lt $COUNT_METADATA_2 ]
then
	echo 1
else
	echo 0
fi

rm -f /tmp/cpu_many_containers_for_10_secs_check_user_list_all*
