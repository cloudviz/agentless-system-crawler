

import urllib2
from plugins.applications.apache import feature
from collections import defaultdict
from utils.crawler_exceptions import CrawlError


def retrieve_status_page(host, port):
    statusPage = "http://%s:%s/server-status?auto" % (host, port)
    req = urllib2.Request(statusPage)
    response = urllib2.urlopen(req)
    return response.read()


def parse_score_board(line, stats):
    switch = {
        "_": 'waiting_for_connection',
        "S": 'starting_up',
        "R": 'reading_request',
        "W": 'sending_reply',
        "K": 'keepalive_read',
        "D": 'dns_lookup',
        "C": 'closing_connection',
        "L": 'logging',
        "G": 'graceful_finishing',
        "I": 'idle_worker_cleanup',
    }
    res = line.split(': ')

    workcounts = defaultdict(int)
    for i in res[1]:
        workcounts[i] += 1

    for x, y in workcounts.iteritems():
        stats[switch.get(x)] = str(y)


def retrieve_metrics(host='localhost', port=80):
    try:
        status = retrieve_status_page(host, port).splitlines()
    except Exception:
        raise CrawlError("can't access to http://%s:%s",
                         host, port)
    switch = {
        "Total kBytes": 'Total_kBytes',
        "Total Accesses": 'Total_Accesses',
        "BusyWorkers": "BusyWorkers",
        "IdleWorkers": "IdleWorkers",
        "BytesPerSec": "BytesPerSec",
        "BytesPerReq": "BytesPerReq",
        "ReqPerSec": "ReqPerSec",
        "Uptime": "Uptime"
    }

    stats = {}

    for line in status:
        if "Scoreboard" in line:
            parse_score_board(line, stats)

        else:
            res = line.split(': ')
            if res[0] in switch:
                stats[switch.get(res[0])] = res[1]

    feature_attributes = feature.ApacheFeature

    if len(stats) == 0:
        raise CrawlError("failure to parse http://%s:%s", host, port)

    for name in feature_attributes._fields:
        if name not in stats:
            stats[name] = '0'

    feature_attributes = feature.get_feature(stats)
    return feature_attributes
