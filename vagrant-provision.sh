#!/bin/bash

# docker as per https://docs.docker.com/installation/ubuntulinux/
apt-key adv --keyserver hkp://pgp.mit.edu:80 \
  --recv-keys 58118E89F3A912897C070ADBF76221572C52609D

echo deb https://apt.dockerproject.org/repo ubuntu-trusty main \
  >> /etc/apt/sources.list.d/docker.list
apt-get update

apt-get -y install docker-engine

# Prereqs for agentless-crawler
apt-get -y install python-dev
apt-get -y install python-pip
pip install simplejson
pip install psutil
pip install netifaces
pip install bottle
