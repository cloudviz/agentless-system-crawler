#!/bin/bash

# Tests the INVM crawler mode
# Returns 1 if success, 0 otherwise

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

# In a VM process with pid 1 should be init
python2.7 ../crawler/crawler.py --crawlmode INVM \
	--features=process | grep -c 'process\s"init/1"'
