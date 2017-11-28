import logging
import time

import psutil

from icrawl_plugin import IVMCrawler
from utils.features import MetricFeature

try:
    import psvmi
except ImportError:
    psvmi = None

logger = logging.getLogger('crawlutils')


class MetricVmCrawler(IVMCrawler):

    """
    To calculate rates like packets sent per second, we need to
    store the last measurement. We store it in this dictionary.
    """

    def __init__(self):
        self._cached_values = {}

    def _cache_put_value(self, key, value):
        self._cached_values[key] = (value, time.time())

    def _cache_get_value(self, key):
        if key in self._cached_values:
            return self._cached_values[key]
        else:
            return None, None

    def _crawl_metrics_cpu_percent(self, process):
        p = process
        cpu_percent = 0

        feature_key = '{0}-{1}'.format('process', p.ident())
        cache_key = '{0}-{1}'.format('OUTVM', feature_key)

        curr_proc_cpu_time, curr_sys_cpu_time = p.get_cpu_times()

        (cputimeList, timestamp) = self._cache_get_value(cache_key)
        self._cache_put_value(
            cache_key, [curr_proc_cpu_time, curr_sys_cpu_time])

        if cputimeList is not None:
            prev_proc_cpu_time = cputimeList[0]
            prev_sys_cpu_time = cputimeList[1]

            if prev_proc_cpu_time and prev_sys_cpu_time:
                if curr_proc_cpu_time == -1 or prev_proc_cpu_time == -1:
                    cpu_percent = -1  # unsupported for this VM
                else:
                    if curr_sys_cpu_time == prev_sys_cpu_time:
                        cpu_percent = 0
                    else:
                        cpu_percent = (float(curr_proc_cpu_time -
                                             prev_proc_cpu_time) * 100 /
                                       float(curr_sys_cpu_time -
                                             prev_sys_cpu_time))

        return cpu_percent

    def crawl(self, vm_desc, **kwargs):

        created_since = -1
        logger.debug('Crawling Metrics')

        if psvmi is None:
            raise NotImplementedError()
        else:
            (domain_name, kernel_version, distro, arch) = vm_desc
            # XXX: this has to be read from some cache instead of
            # instead of once per plugin/feature
            vm_context = psvmi.context_init(
                domain_name, domain_name, kernel_version, distro, arch)
            list = psvmi.process_iter(vm_context)

        for p in list:
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
            ioinfo = (
                p.get_io_counters() if hasattr(
                    p.get_io_counters,
                    '__call__') else p.io_counters)

            cpu_percent = self._crawl_metrics_cpu_percent(p)

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

    def get_feature(self):
        return 'metric'
