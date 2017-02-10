

import urllib2
from plugins.applications.apache import feature
from collections import defaultdict
from utils.crawler_exceptions import CrawlError


def retrieve_status_page(host, port):
    statusPage = "http://%s:%s/server-status?auto" % (host, port)
    req = urllib2.Request(statusPage)
    response = urllib2.urlopen(req)
    return response.read()


def retrieve_metrics(host='localhost', port=80):
    try:
        status = retrieve_status_page(host, port).splitlines()
    except Exception:
        raise CrawlError("can't access to http://%s:%s",
                         host, port)
    stats = {}

    line_num = 0
    for line in status:
        line_num += 1

        if "BusyWorkers" in line:
            res = line.split(': ')
            stats[res[0]] = res[1]
        elif "IdleWorkers" in line:
            res = line.split(': ')
            stats[res[0]] = res[1]
        elif "Scoreboard" in line:
            res = line.split(': ')

            workcounts = defaultdict(int)
            for i in res[1]:
                workcounts[i] += 1

            for x, y in workcounts.iteritems():
                if x == "_":
                    stats['waiting_for_connection'] = str(y)
                elif x == "S":
                    stats['starting_up'] = str(y)
                elif x == "R":
                    stats['reading_request'] = str(y)
                elif x == "W":
                    stats['sending_reply'] = str(y)
                elif x == "K":
                    stats['keepalive_read'] = str(y)
                elif x == "D":
                    stats['dns_lookup'] = str(y)
                elif x == "C":
                    stats['closing_connection'] = str(y)
                elif x == "L":
                    stats['logging'] = str(y)
                elif x == "G":
                    stats['graceful_finishing'] = str(y)
                elif x == "I":
                    stats['idle_worker_cleanup'] = str(y)
        elif "BytesPerSec" in line:
            res = line.split(': ')
            stats[res[0]] = res[1]
        elif "BytesPerReq" in line:
            res = line.split(': ')
            stats[res[0]] = res[1]
        elif "ReqPerSec" in line:
            res = line.split(': ')
            stats[res[0]] = res[1]
        elif "Uptime" in line:
            res = line.split(': ')
            stats[res[0]] = res[1]
        elif "Total kBytes" in line:
            res = line.split(': ')
            stats['Total_kBytes'] = res[1]
        elif "Total Accesses" in line:
            res = line.split(': ')
            stats['Total_Accesses'] = res[1]

    feature_attributes = feature.ApacheFeature

    if len(stats) == 0:
        raise CrawlError("failure to parse http://%s:%s", host, port)

    for name in feature_attributes._fields:
        if name not in stats:
            stats[name] = '0'

    feature_attributes = feature.get_feature(stats)
    return feature_attributes
