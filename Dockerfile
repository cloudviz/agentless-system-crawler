FROM python:2.7

WORKDIR /crawler

COPY crawler/requirements.txt /crawler/requirements.txt
RUN pip install -r requirements.txt

ADD crawler /crawler

ENV DOCKER_VERSION 1.6.2
ADD https://get.docker.com/builds/Linux/x86_64/docker-${DOCKER_VERSION}.tgz /docker.tgz
RUN (cd /; tar xzvf /docker.tgz)

CMD [ "python2.7", "crawler.py" ]
