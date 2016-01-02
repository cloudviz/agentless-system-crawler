#!/bin/bash

# Tests the OUTCONTAINER crawler mode
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

read -d '' METADATA_JSON <<"EOF"
{
    "test_field": 1234,
    "test_field2": "aaaa"
}
EOF
echo "$METADATA_JSON" > /tmp/metadata.json

HOST_IP=`python2.7 -c "$GET_HOST_IP_PY"`
CONTAINER_IMAGE=`docker inspect --format {{.Id}} ubuntu:latest`
CONTAINER_NAME=test_crawl_cpu_container_check_metadata

docker rm -f ${CONTAINER_NAME} 2> /dev/null > /dev/null
docker run -d --name ${CONTAINER_NAME} ${CONTAINER_IMAGE} sleep 60 2> /dev/null > /dev/null
ID=`docker inspect -f '{{ .Id }}' ${CONTAINER_NAME}`

python2.7 ../crawler/crawler.py --crawlmode OUTCONTAINER \
	--features=cpu --crawlContainers $ID \
	--extraMetadataFile /tmp/metadata.json --extraMetadataForAll > /tmp/check_metadata_frame

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
#  "namespace": "10.91.71.246/test_crawl_cpu_container_1",
#  "test_field":123,
#  "test_field2":"aaaa"
#}

TIMESTAMP_DAY_PART=`date +"%Y-%m-%dT"`

grep ^metadata /tmp/check_metadata_frame \
			| grep '"system_type":"container"' \
			| grep '"features":"cpu"' \
			| grep '"timestamp":"'${TIMESTAMP_DAY_PART} \
			| grep '"container_name":"'${CONTAINER_NAME}'"' \
			| grep '"container_image":"'${CONTAINER_IMAGE}'"' \
			| grep '"namespace":"'${HOST_IP}'/'${CONTAINER_NAME}'"' \
			| grep '"test_field":123' \
			| grep '"test_field2":"aaaa"' \
			| grep -c metadata
