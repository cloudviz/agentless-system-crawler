#!/bin/bash

# Tests the OUTCONTAINER crawler mode
# Returns 1 if success, 0 otherwise

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

UUID=`uuidgen`
mkdir -p /bla
touch /bla/$UUID

python2.7 ../../crawler/crawler.py --crawlmode INVM \
	--features=file --options '{"file": {"root_dir": "/bla/"}}' | grep -c "/bla/$UUID"

rm -rf /bla
