# These assume you hav Docker installed and running

all: build test

build:
	docker build -t crawler .

test:
	docker build -t agentless-system-crawler-test -f Dockerfile.test .
	docker run --privileged -ti --rm agentless-system-crawler-test
