import re
import urllib2

from plugins.applications.nginx import feature
from utils.crawler_exceptions import CrawlError


def retrieve_status_page(host, port):
    status_page = "http://%s:%s/nginx_status" % (host, port)
    req = urllib2.Request(status_page)
    response = urllib2.urlopen(req)
    return response.read()


def retrieve_metrics(host='localhost', port=80):
    try:
        status = retrieve_status_page(host, port)
    except Exception:
        raise CrawlError("can't access to http://%s:%s",
                         host, port)

    match1 = re.search(r'Active connections:\s+(\d+)', status)
    match2 = re.search(r'\s*(\d+)\s+(\d+)\s+(\d+)', status)
    match3 = re.search(r'Reading:\s*(\d+)\s*Writing:\s*(\d+)\s*'
                       'Waiting:\s*(\d+)', status)

    try:
        feature_attributes = feature.get_feature(
            match1,
            match2,
            match3)
        return feature_attributes
    except Exception:
        raise CrawlError("failure to parse http://%s:%s", host, port)
