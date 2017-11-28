import logging
import os
import psutil

from dockercontainer import DockerContainer
from icrawl_plugin import IContainerCrawler
from utils.features import MemoryFeature

logger = logging.getLogger('crawlutils')


class MemoryContainerCrawler(IContainerCrawler):

    def get_feature(self):
        return 'memory'

    def _get_cgroup_dir(self, devlist=[]):
        for dev in devlist:
            paths = [os.path.join('/cgroup/', dev),
                     os.path.join('/sys/fs/cgroup/', dev)]
            for path in paths:
                if os.path.ismount(path):
                    return path

            # Try getting the mount point from /proc/mounts
            for l in open('/proc/mounts', 'r'):
                _type, mnt, _, _, _, _ = l.split(' ')
                if _type == 'cgroup' and mnt.endswith('cgroup/' + dev):
                    return mnt

        raise ValueError('Can not find the cgroup dir')

    def get_memory_cgroup_path(self, node='memory.stat'):
        return os.path.join(self._get_cgroup_dir(['memory']), node)

    def crawl(self, container_id, avoid_setns=False, **kwargs):

        used = buffered = cached = free = 'unknown'
        with open(self.get_memory_cgroup_path('memory.stat'
                                                   ), 'r') as f:
            for line in f:
                (key, value) = line.strip().split(' ')
                if key == 'total_cache':
                    cached = int(value)
                if key == 'total_active_file':
                    buffered = int(value)

        with open(self.get_memory_cgroup_path(
                'memory.limit_in_bytes'), 'r') as f:
            limit = int(f.readline().strip())

        with open(self.get_memory_cgroup_path(
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
