import logging
import re
import time

import psutil

from dockercontainer import DockerContainer
from icrawl_plugin import IContainerCrawler
from utils.features import CpuFeature

logger = logging.getLogger('crawlutils')


class CpuContainerCrawler(IContainerCrawler):

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

    def _save_container_cpu_times(self, container_long_id, times):
        cache_key = container_long_id
        self._cache_put_value(cache_key, times)

    def _get_prev_container_cpu_times(self, container_long_id):
        cache_key = container_long_id
        return self._cache_get_value(cache_key)

    def get_feature(self):
        return 'cpu'

    def crawl(self, container_id, avoid_setns=False, per_cpu=False, **kwargs):
        logger.debug(
            'Crawling %s for container %s' %
            (self.get_feature(), container_id))

        container = DockerContainer(container_id)

        host_cpu_feature = {}
        for (idx, cpu) in enumerate(psutil.cpu_times_percent(percpu=True)):
            host_cpu_feature[idx] = CpuFeature(
                cpu.idle,
                cpu.nice,
                cpu.user,
                cpu.iowait,
                cpu.system,
                cpu.irq,
                cpu.steal,
                100 - int(cpu.idle),
            )

        if per_cpu:
            stat_file_name = 'cpuacct.usage_percpu'
        else:
            stat_file_name = 'cpuacct.usage'

        (cpu_usage_t1, prev_time) = (
            self._get_prev_container_cpu_times(container.long_id))

        if cpu_usage_t1:
            logger.debug('Using previous cpu times for container %s'
                         % container.long_id)
            interval = time.time() - prev_time
        else:
            logger.debug(
                'There are no previous cpu times for container %s '
                'so we will be sleeping for 100 milliseconds' %
                container.long_id)

            with open(container.get_cpu_cgroup_path(stat_file_name),
                      'r') as f:
                cpu_usage_t1 = f.readline().strip().split(' ')
            interval = 0.1  # sleep for 100ms
            time.sleep(interval)

        with open(container.get_cpu_cgroup_path(stat_file_name),
                  'r') as f:
            cpu_usage_t2 = f.readline().strip().split(' ')

        # Store the cpu times for the next crawl

        self._save_container_cpu_times(container.long_id,
                                       cpu_usage_t2)

        cpu_user_system = {}
        path = container.get_cpu_cgroup_path('cpuacct.stat')
        with open(path, 'r') as f:
            for line in f:
                m = re.search(r"(system|user)\s+(\d+)", line)
                if m:
                    cpu_user_system[m.group(1)] = \
                        float(m.group(2))

        for (index, cpu_usage_ns) in enumerate(cpu_usage_t1):
            usage_secs = (float(cpu_usage_t2[index]) -
                          float(cpu_usage_ns)) / float(1e9)

            # Interval is never 0 because of step 0 (forcing a sleep)

            usage_percent = usage_secs / interval * 100.0
            if usage_percent > 100.0:
                usage_percent = 100.0
            idle = 100.0 - usage_percent

            # Approximation 1

            user_plus_sys_hz = cpu_user_system['user'] \
                + cpu_user_system['system']
            if user_plus_sys_hz == 0:
                # Fake value to avoid divide by zero.
                user_plus_sys_hz = 0.1
            user = usage_percent * (cpu_user_system['user'] /
                                    user_plus_sys_hz)
            system = usage_percent * (cpu_user_system['system'] /
                                      user_plus_sys_hz)

            # Approximation 2

            nice = host_cpu_feature[index][1]
            wait = host_cpu_feature[index][3]
            interrupt = host_cpu_feature[index][5]
            steal = host_cpu_feature[index][6]
            feature_key = '{0}-{1}'.format('cpu', index)
            feature_attributes = CpuFeature(
                idle,
                nice,
                user,
                wait,
                system,
                interrupt,
                steal,
                usage_percent,
            )
            yield (feature_key, feature_attributes, 'cpu')
