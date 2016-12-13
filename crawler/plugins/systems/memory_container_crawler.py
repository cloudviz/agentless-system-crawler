import logging

import psutil

from dockercontainer import DockerContainer
from icrawl_plugin import IContainerCrawler
from utils.features import MemoryFeature

logger = logging.getLogger('crawlutils')


class MemoryContainerCrawler(IContainerCrawler):

    def get_feature(self):
        return 'memory'

    def crawl(self, container_id, avoid_setns=False, **kwargs):
        container = DockerContainer(container_id)

        used = buffered = cached = free = 'unknown'
        with open(container.get_memory_cgroup_path('memory.stat'
                                                   ), 'r') as f:
            for line in f:
                (key, value) = line.strip().split(' ')
                if key == 'total_cache':
                    cached = int(value)
                if key == 'total_active_file':
                    buffered = int(value)

        with open(container.get_memory_cgroup_path(
                'memory.limit_in_bytes'), 'r') as f:
            limit = int(f.readline().strip())

        with open(container.get_memory_cgroup_path(
                'memory.usage_in_bytes'), 'r') as f:
            used = int(f.readline().strip())

        host_free = psutil.virtual_memory().free
        container_total = used + min(host_free, limit - used)
        free = container_total - used

        if 'unknown' not in [used, free] and (free + used) > 0:
            util_percentage = float(used) / (free + used) * 100.0
        else:
            util_percentage = 'unknown'

        return [('memory', MemoryFeature(used, buffered,
                                         cached, free, util_percentage),
                 'memory')]
