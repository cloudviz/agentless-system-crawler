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

HOST_IP=`python2.7 -c "$GET_HOST_IP_PY" 2> /dev/null`

MSG=`uuid`
NAME=test_crawl_cpu_container_log_links_1
rm -rf /var/log/crawler_container_logs/$HOST_IP/$NAME/
docker rm -f $NAME 2> /dev/null > /dev/null
docker run -d --name $NAME ubuntu bash -c "echo $MSG ; sleep 6000 " 2> /dev/null > /dev/null
ID=`docker inspect -f '{{ .Id }}' $NAME`

python2.7 ../config_and_metrics_crawler/crawler.py --crawlmode OUTCONTAINER \
	--features=cpu --crawlContainers $ID \
	--linkContainerLogFiles --url file:///tmp/$NAME

grep -c $MSG /var/log/crawler_container_logs/$HOST_IP/$NAME/docker.log

docker rm -f $NAME > /dev/null
