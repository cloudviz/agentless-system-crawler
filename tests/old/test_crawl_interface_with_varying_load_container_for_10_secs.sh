#!/bin/bash

# Tests the OUTCONTAINER crawler mode for network traffic for a container with
# varying load. The load is introduced by doing a ping to "localhost".
# The pattern that we check for is: sleep, dd, sleep.  Checking means measuring
# the load from the crawler side, and comparing the pattern we see to what the
# container did.
#
# Returns 1 if success, 0 otherwise

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

read -d '' PARSE_IF_NET_FRAMES_PY <<"EOF"
import sys
import json
import re

tx_arr = []
for line in sys.stdin:
    tx = json.loads(line)["if_packets_tx"]
    tx_arr.append(tx)

# 1. check that our load looks like this: 000011110000
# 	No load for 2+ seconds
#	load for 3+ seconds
#	No load for 2+ seconds
# The regex for this is: 00+11+00+
#print tx_arr
tx_arr_str = ''.join(["1" if tx > 0.1 else "0" for tx in tx_arr])
#print tx_arr_str
p = re.compile('000+111+00+')
match = p.match(tx_arr_str)

# 2. check that the packets tx'ed make an average of 1 per second
tx_arr_load = [tx for tx in tx_arr if tx > 0.0]
tx_arr_load_avg = sum(tx_arr_load) / len(tx_arr_load)
#print tx_arr_load_avg

cond1 = tx_arr_load_avg > 0.8 and tx_arr_load_avg < 3.0
cond2 = match != None

print int(cond1 and cond2)
EOF

docker rm -f test_crawl_interface_container_1 2> /dev/null > /dev/null
docker run -d --name test_crawl_interface_container_1 ubuntu:14.04 \
	bash -c "sleep 15; ping -c5 localhost; sleep 60" 2> /dev/null > /dev/null
ID=`docker inspect -f '{{ .Id }}' test_crawl_interface_container_1`

# Sleep for a bit to not collect some ICMP6 frames that
# always show up in the tcpdumps for the container just
# after it starts.
sleep 10

# The container does: sleep 15, pings localhost for 5 seconds, and then
# goes to sleep.  We start crawling after sleeping 10 seconds, for another 15
# seconds.  So, we should collect this: 5 seconds of 0 network activity,
# followed by 5 seconds of activity, followed by 0 activity.
timeout 17 python2.7 ../config_and_metrics_crawler/crawler.py --crawlmode OUTCONTAINER \
	--features=interface --crawlContainers $ID --frequency 1 | \
	grep interface-lo | awk '{print $3}' | python2.7 -c "${PARSE_IF_NET_FRAMES_PY}"

docker rm -f test_crawl_interface_container_1 > /dev/null
