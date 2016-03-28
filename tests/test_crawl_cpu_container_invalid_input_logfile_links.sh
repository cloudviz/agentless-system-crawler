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
[{"type": null, "name": "/var/log/messages"}, {"type": null, "name": "/etc/csf_env.properties"}, {"type": null, "name": "/var/log/good_log_path.log"}, {"type": null, "name": "docker.log"}]
EOF

#[{"type": null, "name": "/var/log/messages"}, {"type": null, "name": "/etc/csf_env.properties"}, {"type": null, "name": "/var/log/input_file_name.log"}, {"type": null, "name": "docker.log"}]
HOST_IP=`python2.7 -c "$GET_HOST_IP_PY" 2> /dev/null`

MSG=`uuid`
NAME=test_crawl_cpu_container_log_links_1
rm -rf /var/log/crawler_container_logs/$HOST_IP/$NAME/
docker rm -f $NAME 2> /dev/null > /dev/null

BAD_LOG_PATH_1=/var/log/../log/`uuid`.log
BAD_LOG_PATH_2=../log/`uuid`.log
GOOD_LOG_PATH=/var/log/good_log_path.log

docker run -d -e LOG_LOCATIONS=${BAD_LOG_PATH_1},${GOOD_LOG_PATH},${BAD_LOG_PATH_2} --name $NAME \
	ubuntu bash -c "echo $MSG >> ${BAD_LOG_PATH_1}; echo $MSG >> /var/log/messages; echo $MSG; echo $MSG >> ${GOOD_LOG_PATH}; sleep 6000 " 2> /dev/null > /dev/null
ID=`docker inspect -f '{{ .Id }}' $NAME`

python2.7 ../config_and_metrics_crawler/crawler.py --crawlmode OUTCONTAINER \
	--features=cpu --crawlContainers $ID \
	--linkContainerLogFiles --url file:///tmp/$NAME

# should be 1
LOG_COUNT_1=`grep -c $MSG /var/log/crawler_container_logs/$HOST_IP/$NAME/var/log/messages`
# should be 1
LOG_COUNT_2=`grep -c $MSG /var/log/crawler_container_logs/$HOST_IP/$NAME/docker.log`
# should be 1
LOG_COUNT_3=`grep -c $MSG /var/log/crawler_container_logs/$HOST_IP/$NAME/${GOOD_LOG_PATH}`

printf "$JSON_LOG_TYPES" > /tmp/json_log_types
# should be 0
DIFF_COUNT=`diff -q /tmp/json_log_types /var/log/crawler_container_logs/$HOST_IP/$NAME/d464347c-3b99-11e5-b0e9-062dcffc249f.type-mapping | wc -l`

# should be 1
GREP_COUNT_1=`grep "User provided a log file path that is not absolute: $BAD_LOG_PATH_1" *.log | wc -l`
# should be 1
GREP_COUNT_2=`grep "User provided a log file path that is not absolute: $BAD_LOG_PATH_2" *.log | wc -l`

#  /var/log/crawler_container_logs/$HOST_IP/$NAME/var/log/input_file_name.log should not be linked
if [ ! -f /var/log/crawler_container_logs/$HOST_IP/$NAME/var/log/input_file_name.log ] && \
   [ $LOG_COUNT_1 == "1" ] && [ $LOG_COUNT_2 == "1" ] && [ $LOG_COUNT_3 == "1" ] && \
   [ $DIFF_COUNT == "0" ] && [ $GREP_COUNT_1 == "1" ] && [ $GREP_COUNT_2 == "1" ]
then
	echo 1
else
	echo 0
fi

docker rm -f $NAME > /dev/null
