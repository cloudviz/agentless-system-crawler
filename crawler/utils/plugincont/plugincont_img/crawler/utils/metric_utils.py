import os
import psutil
from collections import namedtuple
from utils.features import MetricFeature


def _crawl_metrics_cpu_percent(process):
    cpu_percent = (
        process.get_cpu_percent(
            interval=0) if hasattr(
            process.get_cpu_percent,
            '__call__') else process.cpu_percent)
    return cpu_percent


def crawl_metrics():
    created_since = -1

    for p in psutil.process_iter():
        create_time = (
            p.create_time() if hasattr(
                p.create_time,
                '__call__') else p.create_time)
        if create_time <= created_since:
            continue

        name = (p.name() if hasattr(p.name, '__call__'
                                    ) else p.name)
        pid = (p.pid() if hasattr(p.pid, '__call__') else p.pid)
        status = (p.status() if hasattr(p.status, '__call__'
                                        ) else p.status)
        if status == psutil.STATUS_ZOMBIE:
            continue
        username = (
            p.username() if hasattr(
                p.username,
                '__call__') else p.username)
        meminfo = (
            p.get_memory_info() if hasattr(
                p.get_memory_info,
                '__call__') else p.memory_info)
        try:
            ioinfo = (
                p.get_io_counters() if hasattr(
                    p.get_io_counters,
                    '__call__') else p.io_counters)
        except psutil.AccessDenied:
            selfpid = os.getpid()
            if pid != selfpid:
                # http://lukasz.langa.pl/5/error-opening-file-for-reading-permission-denied/
                print "got psutil.AccessDenied for pid:", pid
            ioinfo = namedtuple('ioinfo', ['read_count', 'write_count',
                         'read_bytes', 'write_bytes'])
            ioinfo.read_bytes = 0
            ioinfo.write_bytes = 0 

        cpu_percent = _crawl_metrics_cpu_percent(p)

        memory_percent = (
            p.get_memory_percent() if hasattr(
                p.get_memory_percent,
                '__call__') else p.memory_percent)

        feature_key = '{0}/{1}'.format(name, pid)
        yield (feature_key, MetricFeature(
            round(cpu_percent, 2),
            round(memory_percent, 2),
            name,
            pid,
            ioinfo.read_bytes,
            meminfo.rss,
            str(status),
            username,
            meminfo.vms,
            ioinfo.write_bytes,
        ), 'metric')
