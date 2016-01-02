#!/bin/bash

# Tests the --linkContainerLogFiles option for the OUTCONTAINERcrawler mode .
# This option maintains symlinks for some logfiles inside the container. By
# default /var/log/messages and the docker (for all containers) are symlinked
# to a central location: /var/log/crawl_container_logs/...
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

read -d '' JSON_LOG_TYPES <<"EOF"
[{"type": null, "name": "/var/log/messages"}, {"type": null, "name": "/var/log/input_file_name.log"}, {"type": null, "name": "docker.log"}]
EOF

HOST_IP=`python2.7 -c "$GET_HOST_IP_PY" 2> /dev/null`

MSG=`uuid`
NAME=test_crawl_cpu_container_log_links_1
rm -rf /var/log/crawler_container_logs/$HOST_IP/$NAME/
docker rm -f $NAME 2> /dev/null > /dev/null

docker run -d -e LOG_LOCATIONS=/var/log/input_file_name.log --name $NAME \
	ubuntu bash -c "echo $MSG >> /var/log/input_file_name.log; sleep 5; echo $MSG >> /var/log/input_file_name.log; sleep 6000 " 2> /dev/null > /dev/null
ID=`docker inspect -f '{{ .Id }}' $NAME`

timeout 10 python2.7 ../crawler/crawler.py --crawlmode OUTCONTAINER \
	--features=cpu --frequency 1 \
	--linkContainerLogFiles --url file:///tmp/$NAME

LOG_COUNT=`grep -c $MSG /var/log/crawler_container_logs/$HOST_IP/$NAME/var/log/input_file_name.log`

printf "$JSON_LOG_TYPES" > /tmp/json_log_types
DIFF_COUNT=`diff -q /tmp/json_log_types /var/log/crawler_container_logs/$HOST_IP/$NAME/d464347c-3b99-11e5-b0e9-062dcffc249f.type-mapping | wc -l`

if [ $LOG_COUNT == "2" ] && [ $DIFF_COUNT == "0" ]
then
	echo 1
else
	echo 0
fi

docker rm -f $NAME > /dev/null
