#!/bin/bash

# Tests the OUTCONTAINER crawler mode for 32 containers
# Returns 1 if success, 0 otherwise

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

CRAWLER_CODE=../../crawler/crawler.py

cat > /tmp/dummy-metadata-file << EOF
{"uuid": "<UUID>", "availability_zone": "nova", "hostname": "li-l6o5-3mvyy3m5ug3l-r2wazwiucexe-server-52l5wrw5277b.novalocal", "launch_index": 0, "meta": {"Cmd_0": "echo \"Hello world\"", "tagseparator": "_", "sgroup_name": "lindj_group1", "logging_password": "VSKHimqp69Nk", "Cmd_1": "/bin/bash", "tenant_id": "<SPACE_ID>", "testvar1": "testvalue1", "sgroup_id": "dd28638d-7c10-4e26-9059-6e0baba7f64d", "test2": "supercoolvar2", "logstash_target": "logmet.stage1.opvis.bluemix.net:9091", "tagformat": "tenant_id group_id uuid", "metrics_target": "logmet.stage1.opvis.bluemix.net:9095", "group_id": "0000"}, "name": "li-l6o5-3mvyy3m5ug3l-r2wazwiucexe-server-52l5wrw5277b"}
EOF


COUNT=4

for i in `seq 1 $COUNT`
do
	SPACE_ID[$i]=`uuidgen`
	CONTAINER_ID[$i]=`uuidgen`
	MSG=${CONTAINER_ID[$i]}

	docker rm -f test_crawl_cpu_many_containers_$i 2> /dev/null > /dev/null
	docker run -d -e LOG_LOCATIONS=/var/log/input_file_name.log --name test_crawl_cpu_many_containers_$i \
		ubuntu bash -c "echo $MSG >> /var/log/input_file_name.log; echo $MSG; sleep 5; echo $MSG >> /var/log/input_file_name.log; echo $MSG; sleep 6000 " 2> /dev/null > /dev/null
	DOCKER_ID=`docker inspect -f '{{ .Id }}' test_crawl_cpu_many_containers_$i`

	# Create dummy metadata file
	mkdir -p /openstack/nova/metadata/
	cp /tmp/dummy-metadata-file /openstack/nova/metadata/${DOCKER_ID}.json
	sed -i s"/<UUID>/${CONTAINER_ID[$i]}/" /openstack/nova/metadata/${DOCKER_ID}.json
	sed -i s"/<SPACE_ID>/${SPACE_ID[$i]}/" /openstack/nova/metadata/${DOCKER_ID}.json
done

IDS=`docker ps | grep test_crawl_cpu_many_containers | awk '{printf "%s,",  $1}' | sed s/,$//g`

rm -rf /tmp/alchemy_all_test*

python2.7 ${CRAWLER_CODE} --crawlmode OUTCONTAINER \
	--features=cpu,memory,interface --crawlContainers $IDS --numprocesses 4 \
	--frequency 0 --environment alchemy --format graphite \
	--url file:///tmp/alchemy_all_test 2> /dev/null > /dev/null &
PID_PARENT=$!

sleep 3
FIRST_CHILD=`pgrep -P $PID_PARENT | head -n 1 | awk '{print $1}'`
sleep 3

exec 2> /dev/null
kill -9 $FIRST_CHILD
sleep 5

# the only crawler process is "grep crawler" so COUNT_CRAWLER is 1
COUNT_CRAWLER=`ps aux | grep crawler | wc -l`

for i in `seq 1 $COUNT`
do
	docker rm -f test_crawl_cpu_many_containers_$i > /dev/null
done

if [ $COUNT_CRAWLER == "1" ]
then
	echo 1
else
	echo 0
fi
