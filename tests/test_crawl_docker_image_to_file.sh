#!/bin/bash

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi


SHORT_IMAGE_NAME=kollerr-test-1
TAG=test-tag
REGISTRY=registry.stage1.ng.bluemix.net
IMAGE=${REGISTRY}/kollerr/${SHORT_IMAGE_NAME}:${TAG}
FRAME=/tmp/`uuid`
NOTIFICATION_URL=none
CONTAINER_NAME=container-`uuid`
NAMESPACE=$IMAGE
OWNER_NAMESPACE=owner-`uuid`
REQUEST_ID=`uuid`
INSTANCE_ID=regcrawler-`uuid`
OUTPUT=/tmp/crawl_docker_image.out
TMP_OUT=/tmp/`uuid`


# Temporarily create an image that looks like a bluemix image
docker tag ubuntu:latest $IMAGE

(cd ../config_and_metrics_crawler/.
bash crawl_docker_image.sh \
	$IMAGE \
	file://$FRAME \
	$NOTIFICATION_URL \
	$CONTAINER_NAME \
	$NAMESPACE \
	$OWNER_NAMESPACE \
	$REQUEST_ID \
	$INSTANCE_ID > $OUTPUT
)

# OUTPUT should look like this:
# 406802c8-9f6f-11e5-a640-06427acb060b Running crawler.py
# 406802c8-9f6f-11e5-a640-06427acb060b Successfully crawled and frame emitted.
# 406802c8-9f6f-11e5-a640-06427acb060b Removing container 40698576-9f6f-11e5-aeed-06427acb060b
COUNT1=`grep -c "$REQUEST_ID Running crawler.py" $OUTPUT`
COUNT2=`grep -c "$REQUEST_ID Successfully crawled and frame emitted" $OUTPUT`
COUNT3=`grep -c "$REQUEST_ID Removing container" $OUTPUT`

grep ^metadata ${FRAME}.* | grep '"uuid":"'$REQUEST_ID'"' \
			| grep '"namespace":"'$NAMESPACE'"' \
			| grep '"owner_namespace":"'$OWNER_NAMESPACE'"' \
			| grep '"docker_image_short_name":"'${SHORT_IMAGE_NAME}':'${TAG}'"' \
			| grep '"docker_image_long_name":"'${IMAGE}'"' \
			| grep '"docker_image_tag":"'${TAG}'"' \
			| grep '"docker_image_registry":"'${REGISTRY}'"' \
			| grep -c metadata > $TMP_OUT

COUNT4=`head -n 1 $TMP_OUT`

if [ $COUNT1 == "1" ] && [ $COUNT2 == "1" ] && [ $COUNT3 == "1" ] && [ $COUNT4 == "1" ]
then
	echo 1
else
	echo 0
fi

docker rmi $IMAGE 2> /dev/null > /dev/null
rm -f ${FRAME}.*
rm -f ${OUTPUT}
rm -f $TMP_OUT
