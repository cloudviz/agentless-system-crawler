#!/bin/bash

# Start the crawler as a container.

# Arguments passed to this script will be passed to the crawler.

CRAWLER_ARGS=`echo $@ | awk '{for (i = 2; i <= NF; i++) print $i}'`

case "$1" in
	help*)
		docker run -it crawler --help
	;;
	host*)
		docker run \
			--privileged \
			--net=host \
			--pid=host \
			-v /cgroup:/cgroup:ro \
                        -v /var/lib/docker:/var/lib/docker:ro \
			-v /sys/fs/cgroup:/sys/fs/cgroup:ro \
			-v /var/run/docker.sock:/var/run/docker.sock \
			-it crawler --crawlmode INVM ${CRAWLER_ARGS}
	;;
	containers*)
		docker run \
			--privileged \
			--net=host \
			--pid=host \
			-v /cgroup:/cgroup:ro \
                        -v /var/lib/docker:/var/lib/docker:ro \
			-v /sys/fs/cgroup:/sys/fs/cgroup:ro \
			-v /var/run/docker.sock:/var/run/docker.sock \
			-it crawler --crawlmode OUTCONTAINER ${CRAWLER_ARGS}
	;;
	none*)
		docker run \
			--privileged \
			--net=host \
			--pid=host \
			-v /cgroup:/cgroup:ro \
			-v /sys/fs/cgroup:/sys/fs/cgroup:ro \
			-v /var/run/docker.sock:/var/run/docker.sock \
			--entrypoint=/bin/bash \
			-it crawler
	;;
        *)
		echo $"Usage: $0 {host|containers|help|none}"
		exit 1
esac
