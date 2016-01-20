#!/bin/bash

# Tests the cloudsight environment.  2 containers are created, one ready for
# alchemy, and one not. Check that only the non-alchemy one is crawled.  Returns 1
# if success, 0 otherwise

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

# The namespace generated for the crawled container looks like <HOST_IP>/<CONTAINER_NAME>
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

cat > /tmp/dummy-metadata-file << EOF
{"uuid": "<UUID>", "availability_zone": "nova", "hostname": "li-l6o5-3mvyy3m5ug3l-r2wazwiucexe-server-52l5wrw5277b.novalocal", "launch_index": 0, "meta": {"Cmd_0": "echo \"Hello world\"", "tagseparator": "_", "sgroup_name": "lindj_group1", "logging_password": "VSKHimqp69Nk", "Cmd_1": "/bin/bash", "tenant_id": "<SPACE_ID_1>", "testvar1": "testvalue1", "sgroup_id": "dd28638d-7c10-4e26-9059-6e0baba7f64d", "test2": "supercoolvar2", "logstash_target": "logmet.stage1.opvis.bluemix.net:9091", "tagformat": "tenant_id group_id uuid", "metrics_target": "logmet.stage1.opvis.bluemix.net:9095", "group_id": "0000"}, "name": "li-l6o5-3mvyy3m5ug3l-r2wazwiucexe-server-52l5wrw5277b"}
EOF


HOST_IP=`python2.7 -c "$GET_HOST_IP_PY"`
CONTAINER_NAME_1=test_crawl_check_environment_alchemy_1
CONTAINER_NAME_2=test_crawl_check_environment_alchemy_2
CONTAINER_IMAGE=`docker inspect --format {{.Id}} ubuntu:latest`

# start container 1 (alchemy)
docker rm -f ${CONTAINER_NAME_1} 2> /dev/null > /dev/null
docker run -d --name ${CONTAINER_NAME_1} ${CONTAINER_IMAGE} sleep 60 2> /dev/null > /dev/null
DOCKER_ID_1=`docker inspect -f '{{ .Id }}' ${CONTAINER_NAME_1}`

# start container 2 (not-alchemy)
docker rm -f ${CONTAINER_NAME_2} 2> /dev/null > /dev/null
docker run -d --name ${CONTAINER_NAME_2} ${CONTAINER_IMAGE} sleep 60 2> /dev/null > /dev/null
DOCKER_ID_2=`docker inspect -f '{{ .Id }}' ${CONTAINER_NAME_2}`

# Create dummy metadata file for container DOCKER_ID_1
CONTAINER_ID_1=`uuid`
SPACE_ID_1=`uuid`
sed -i s"/<UUID>/${CONTAINER_ID_1}/" /tmp/dummy-metadata-file
sed -i s"/<SPACE_ID_1>/${SPACE_ID_1}/" /tmp/dummy-metadata-file
mkdir -p /openstack/nova/metadata/
mv /tmp/dummy-metadata-file /openstack/nova/metadata/${DOCKER_ID_1}.json

python2.7 ../config_and_metrics_crawler/crawler.py --crawlmode OUTCONTAINER \
	--features=cpu --crawlContainers $DOCKER_ID_1,$DOCKER_ID_2 \
	--environment cloudsight > /tmp/check_metadata_frame

NAMESPACE_1=${HOST_IP}/${CONTAINER_NAME_1}
NAMESPACE_1_ALCHEMY_FORMAT=${SPACE_ID_1}_0000_${CONTAINER_ID_1}
NAMESPACE_2=${HOST_IP}/${CONTAINER_NAME_2}

# should only have one as there will only be one container crawled (container-2)
N1=`grep -c cpu-0 /tmp/check_metadata_frame`
N2=`grep -c ^metadata /tmp/check_metadata_frame`
N3=`grep -c '"namespace":"'${NAMESPACE_1}'"' /tmp/check_metadata_frame`
N4=`grep -c '"namespace":"'${NAMESPACE_1_ALCHEMY_FORMAT}'"' /tmp/check_metadata_frame`
N5=`grep -c '"namespace":"'${NAMESPACE_2}'"' /tmp/check_metadata_frame`

docker rm -f ${CONTAINER_NAME_1} > /dev/null
docker rm -f ${CONTAINER_NAME_2} > /dev/null

# Both containers should be crawled: N1=2 and N2=2
# Container 1 should be crawled, and its namespace should be in cloudsight format: N3=1 and N4=0
# Container 2 should be crawled, and its namespace should be in cloudsight format: N5=1
if [ $N1 == "2" ] && [ $N2 == "2" ] && [ $N3 == "1" ] && [ $N4 == "0" ] && [ $N5 == "1" ]
then
	echo 1
else
	echo 0
fi
