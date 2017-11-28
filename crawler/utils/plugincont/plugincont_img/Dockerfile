FROM python:2.7

WORKDIR /crawler

COPY requirements.txt /crawler/requirements.txt
RUN pip install -r requirements.txt

COPY \
  dependencies/python-socket-datacollector_0.1.4-1_all.deb \
  dependencies/softflowd_0.9.9902-1_amd64.deb \
  dependencies/python-conntrackprobe_0.2.1-1_all.deb \
  /tmp/

RUN dpkg -i /tmp/python-socket-datacollector_*_all.deb && \
    apt-get -y update && \
    apt-get -y install libpcap0.8 && \
    dpkg -i /tmp/softflowd_0.9.*_amd64.deb && \
    pip install pyroute2 py-radix requests-unixsocket json-rpc && \
    dpkg -i /tmp/python-conntrackprobe_*_all.deb && \
    rm -f /tmp/*.deb

ENV PYTHONPATH=/usr/lib/python2.7/dist-packages:/usr/local/lib/python2.7/site-packages

ADD crawler /crawler

RUN groupadd -r user1 -g 1000 && \
    useradd -u 1000 -m user1 -g user1 && \
    usermod -a -G user1 user1 && \
    chsh -s /bin/bash user1

RUN sed -i s/" and isfile_strict(file):"/:/ /usr/local/lib/python2.7/site-packages/psutil/_pslinux.py

