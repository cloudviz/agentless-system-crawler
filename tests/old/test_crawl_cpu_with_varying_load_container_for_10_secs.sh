#!/bin/bash

# Tests the OUTCONTAINER crawler mode for CPU for a container with varying
# load. The load is introduced by doing a heavy 'dd'.  The pattern that we
# check for is: sleep, dd, sleep. Checking means measuring the load from the
# crawler side, and comparing the pattern we see to what the container did.
#
# Returns 1 if success, 0 otherwise

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

read -d '' PARSE_CPU_FRAMES_PY <<"EOF"
import sys
import json
import re

cpu_sys_arr = []
for line in sys.stdin:
    cpu_sys = json.loads(line)["cpu_system"]
    cpu_sys_arr.append(cpu_sys)

# 1. check that our load looks like this: 00000111100000
# 	No load for 2+ seconds
#	load for 3+ seconds
#	No load for 2+ seconds
# The regex for this is: 00+111+00+
#print cpu_sys_arr
cpu_sys_arr_str = ''.join(["1" if cpu_sys > 5.0 else "0" for cpu_sys in cpu_sys_arr])
#print cpu_sys_arr_str
p = re.compile('00+111+00+')
match = p.match(cpu_sys_arr_str)

# 2. check that the packets cpu_sys'ed make an average of 1 per second
cpu_sys_arr_load = [cpu_sys for cpu_sys in cpu_sys_arr if cpu_sys > 0.0]
cpu_sys_arr_load_sum = sum(cpu_sys_arr_load)

cond1 = cpu_sys_arr_load_sum > (50*3)
#print cpu_sys_arr_load_sum
cond2 = match != None

print int(cond1 and cond2)
EOF

docker rm -f test_crawl_cpu_container_1 2> /dev/null > /dev/null
docker run -d --name test_crawl_cpu_container_1 ubuntu \
	bash -c "sleep 15; timeout 5 dd if=/dev/zero of=/dev/null; sleep 60" 2> /dev/null > /dev/null
ID=`docker inspect -f '{{ .Id }}' test_crawl_cpu_container_1`

# Sleep for a bit to make sure the contianer is just sleeping and not loading
# the sleep binary or something like that.
sleep 10

# The container does: sleep 15, does a 'dd' for 5 seconds and then sleeps.  We
# start crawling after sleeping 10 seconds, for another 15 seconds.  So, we
# should collect this: 5 seconds of 0 network activity, followed by 5 seconds
# of activity, and then no activity.
timeout 15 python2.7 ../../crawler/crawler.py --crawlmode OUTCONTAINER \
	--features=cpu --crawlContainers $ID --frequency 1 | \
	grep cpu-0 | awk '{print $3}' | python2.7 -c "${PARSE_CPU_FRAMES_PY}"

docker rm -f test_crawl_cpu_container_1 > /dev/null
