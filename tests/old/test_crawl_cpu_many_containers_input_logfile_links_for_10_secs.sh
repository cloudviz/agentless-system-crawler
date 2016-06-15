#!/bin/bash

# Tests the OUTCONTAINER crawler mode for 32 containers
# Returns 1 if success, 0 otherwise

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

# The docker log link will be created here:
# /var/log/crawler_container_logs/<HOST_IP>/<CONTAINER_NAME>/docker.log
# I have some python code to get the local host IP. XXX replace it with bash
read -d '' GET_HOST_IP_PY <<"EOF"
import socket
def get_host_ipaddr():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('www.ibm.com', 9))
        return s.getsockname()[0]
    except socket.error:
        return socket.gethostname()
    finally: 
        del s
print get_host_ipaddr()
EOF

HOST_IP=`python2.7 -c "$GET_HOST_IP_PY"`

COUNT=4
MSG=`uuid`

for i in `seq 1 $COUNT`
do
	rm -rf /var/log/crawler_container_logs/$HOST_IP/test_crawl_cpu_many_containers_$i
	docker rm -f test_crawl_cpu_many_containers_$i 2> /dev/null > /dev/null
	docker run -d -e LOG_LOCATIONS=/var/log/input_file_name.log --name test_crawl_cpu_many_containers_$i \
		ubuntu bash -c "echo $MSG >> /var/log/input_file_name.log ; sleep 5 ; echo $MSG >> /var/log/input_file_name.log ; sleep 6000 " 2> /dev/null > /dev/null
done

IDS=`docker ps | grep test_crawl_cpu_many_containers | awk '{printf "%s,",  $1}' | sed s/,$//g`

timeout 10 python2.7 ../config_and_metrics_crawler/crawler.py --crawlmode OUTCONTAINER \
	--features=cpu --crawlContainers $IDS --numprocesses 2 \
	--linkContainerLogFiles --frequency 1 2> /dev/null > /dev/null

COUNT2=0
for i in `seq 1 $COUNT`
do
	R=`grep -c $MSG /var/log/crawler_container_logs/$HOST_IP/test_crawl_cpu_many_containers_$i/var/log/input_file_name.log`
	COUNT2=$(($COUNT2 + $R))
done

for i in `seq 1 $COUNT`
do
	docker rm -f test_crawl_cpu_many_containers_$i > /dev/null
done

# In those 10 seconds, the containers had 2 logs
COUNT=$(($COUNT * 2))
if [ $COUNT == $COUNT2 ]
then
	echo 1
else
	echo 0
fi
