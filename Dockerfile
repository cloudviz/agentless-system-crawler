FROM ubuntu
RUN apt-get -y update && apt-get -y upgrade
RUN apt-get install -y build-essential checkinstall \
    libreadline-gplv2-dev libncursesw5-dev libssl-dev libsqlite3-dev \
    tk-dev libgdbm-dev libc6-dev libbz2-dev \
    wget

ENV pyVer=2.7.5
RUN cd /tmp && \
    wget http://python.org/ftp/python/$pyVer/Python-${pyVer}.tgz && \
    tar -xvf Python-${pyVer}.tgz && \
    cd Python-${pyVer} && \
    ./configure && \
    make && \
    checkinstall && \
    rm -rf /tmp/*

RUN apt-get install -y python-dev python-pip
RUN pip install psutil && \
    pip install netifaces && \
    pip install bottle && \
    pip install requests && \
    pip install python-dateutil

RUN mkdir /crawler
COPY . /crawler/
WORKDIR /crawler/

ENTRYPOINT [ "python", "crawler/crawler.py" ]
