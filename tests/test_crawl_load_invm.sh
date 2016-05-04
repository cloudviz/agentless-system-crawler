#!/bin/bash

# Tests the OUTCONTAINER crawler mode
# Returns 1 if success, 0 otherwise

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

python2.7 ../config_and_metrics_crawler/crawler.py --crawlmode INVM \
	--features=load | grep -c shortterm
