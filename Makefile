# These assume you hav Docker installed and running
SHELL = bash

all: build test

build:
	docker build -t crawler .

test:
	@if [ ! -d psvmi ]; then git clone https://github.com/cloudviz/psvmi.git; fi
	docker build -t agentless-system-crawler-test -f Dockerfile.test.sahil .
	docker run --privileged --pid=host -ti --rm agentless-system-crawler-test
