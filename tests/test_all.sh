#!/bin/bash

GREEN='\033[1;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

DEBUG=0

for i in `ls test*.sh | grep -v test_all.sh | grep -v kafka | grep -v test_alchemy_crawler_services`
do
	printf "%s " $i
        if [ $DEBUG == "1" ]
	then
		R=`bash -x $i`
	else
		R=`bash $i`
	fi
	if [ $R == "1" ]
	then
		printf "${GREEN}%s${NC}\n" $R
	else
		printf "${RED}%s${NC}\n" $R
        	if [ $DEBUG == "1" ]
		then
			exit
		fi
	fi
done

python2.7 test_dockerutils.py
python2.7 test_emitter.py
python2.7 test_features_crawler.py
python2.7 test_namespace.py

