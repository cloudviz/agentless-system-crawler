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

HOST_NAMESPACE=dev-test
MSG=`uuid`
NAME=test_crawl_nofeatures_container_input_logfile_links_for_10_secs
rm -rf /var/log/crawler_container_logs/dev-test*
docker rm -f $NAME 2> /dev/null > /dev/null
	docker run -d -e LOG_LOCATIONS=/var/log/input_file_name.log --name $NAME \
		ubuntu bash -c "echo $MSG >> /var/log/input_file_name.log; \
                                echo CLOUD_APP_GROUP=\'watson_test\' >>/etc/csf_env.properties; \
                                echo CLOUD_APP=\'service_1\' >>/etc/csf_env.properties; \
                                echo CLOUD_TENANT=\'public\' >>/etc/csf_env.properties; \
                                echo CLOUD_AUTO_SCALE_GROUP=\'service_v003\' >>/etc/csf_env.properties; \
                                echo CRAWLER_METRIC_PREFIX=watson_test.service_1.service_v003  >>/etc/csf_env.properties; \
                                sleep 6000" 2> /dev/null > /dev/null

timeout 10 python2.7 ../config_and_metrics_crawler/crawler.py --crawlmode OUTCONTAINER \
	--features=nofeatures --crawlContainers ${DOCKER_ID} \
	--linkContainerLogFiles --frequency 1 \
	--environment watson --namespace ${HOST_NAMESPACE} 2> /dev/null > /dev/null

ID1=`docker ps | grep $NAME | awk '{print $1}'`

sleep 10

# By now the log should be there                                                                                                            
test_log_fc=`find /var/log/crawler_container_logs/${HOST_NAMESPACE}.watson_test.service_1.service_v003.$ID1/* | grep -c "input_file_name"`

if [ $test_log_fc == 0 ];
then
    echo 0;
else
    echo 1
fi

docker rm -f $NAME > /dev/null
rm -rf /var/log/crawler_container_logs/dev-test.*
