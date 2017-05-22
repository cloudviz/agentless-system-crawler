FROM python:2.7

WORKDIR /crawler

COPY requirements.txt /crawler/requirements.txt
RUN pip install -r requirements.txt

COPY \
  dependencies/python-socket-datacollector_0.1.1-1_all.deb \
  dependencies/softflowd_0.9.9902-1_amd64.deb \
  /tmp/
RUN dpkg -i /tmp/python-socket-datacollector_*_all.deb && \
    apt-get -y update && \
    apt-get -y install libpcap0.8 && \
    dpkg -i /tmp/softflowd_0.9.*amd64.deb && \
    rm -f /tmp/*.deb

ADD crawler /crawler

ENTRYPOINT [ "python2.7", "crawler.py" ]
