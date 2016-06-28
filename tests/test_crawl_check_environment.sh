#!/bin/bash

# Tests the alchemy environment.
# 2 containers are created, one ready for alchemy, and one not. Check that only the alchemy one is crawled.
# Returns 1 if success, 0 otherwise

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
{"uuid": "<UUID>", "availability_zone": "nova", "hostname": "li-l6o5-3mvyy3m5ug3l-r2wazwiucexe-server-52l5wrw5277b.novalocal", "launch_index": 0, "meta": {"Cmd_0": "echo \"Hello world\"", "tagseparator": "_", "sgroup_name": "lindj_group1", "logging_password": "VSKHimqp69Nk", "Cmd_1": "/bin/bash", "tenant_id": "<SPACE_ID>", "testvar1": "testvalue1", "sgroup_id": "dd28638d-7c10-4e26-9059-6e0baba7f64d", "test2": "supercoolvar2", "logstash_target": "logmet.stage1.opvis.bluemix.net:9091", "tagformat": "tenant_id group_id uuid", "metrics_target": "logmet.stage1.opvis.bluemix.net:9095", "group_id": "0000"}, "name": "li-l6o5-3mvyy3m5ug3l-r2wazwiucexe-server-52l5wrw5277b"}
EOF


HOST_IP=`python2.7 -c "$GET_HOST_IP_PY"`
CONTAINER_NAME=test_crawl_cpu_container_check_metadata
CONTAINER_IMAGE=`docker inspect --format {{.Id}} ubuntu:latest`

docker rm -f ${CONTAINER_NAME} 2> /dev/null > /dev/null
docker run -d --name ${CONTAINER_NAME} ${CONTAINER_IMAGE} sleep 60 2> /dev/null > /dev/null
DOCKER_ID=`docker inspect -f '{{ .Id }}' ${CONTAINER_NAME}`

# Create dummy metadata file for container DOCKER_ID
CONTAINER_ID=`uuid`
SPACE_ID=`uuid`
sed -i s"/<UUID>/${CONTAINER_ID}/" /tmp/dummy-metadata-file
sed -i s"/<SPACE_ID>/${SPACE_ID}/" /tmp/dummy-metadata-file
mkdir -p /openstack/nova/metadata/
mv /tmp/dummy-metadata-file /openstack/nova/metadata/${DOCKER_ID}.json

python2.7 ../config_and_metrics_crawler/crawler.py --crawlmode OUTCONTAINER \
	--features=cpu --crawlContainers $DOCKER_ID \
	--environment alchemy > /tmp/check_metadata_frame

docker rm -f ${CONTAINER_NAME} > /dev/null

#{
#  "since_timestamp": 1445848019,
#  "container_long_id": "ec120e72846942d3f0805a5facf17d24982dd54c9ebb78367cc0b9ff0dfb9019",
#  "features": "cpu",
#  "timestamp": "2015-12-11T09:51:37-0600",
#  "since": "BOOT",
#  "compress": false,
#  "system_type": "container",
#  "container_name": "test_crawl_cpu_container_1",
#  "container_image": "ca4d7b1b9a51f72ff4da652d96943f657b4898889924ac3dae5df958dba0dc4a",
#  "namespace": "10.91.71.246/test_crawl_cpu_container_1"
#}

TIMESTAMP_DAY_PART=`date +"%Y-%m-%dT"`
NAMESPACE=${SPACE_ID}.0000.${CONTAINER_ID}

grep ^metadata /tmp/check_metadata_frame \
			| grep '"system_type":"container"' \
			| grep '"features":"cpu"' \
			| grep '"timestamp":"'${TIMESTAMP_DAY_PART} \
			| grep '"container_name":"'${CONTAINER_NAME}'"' \
			| grep '"container_image":"'${CONTAINER_IMAGE}'"' \
			| grep '"namespace":"'${NAMESPACE}'"' \
			| grep -c metadata

rm -f /openstack/nova/metadata/${DOCKER_ID}.json
