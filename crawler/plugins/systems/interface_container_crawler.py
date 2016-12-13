import logging
import time

import psutil

from dockercontainer import DockerContainer
from icrawl_plugin import IContainerCrawler
from utils.features import InterfaceFeature
from utils.namespace import run_as_another_namespace

logger = logging.getLogger('crawlutils')


class InterfaceContainerCrawler(IContainerCrawler):

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

    def _crawl_interface_counters(self):
        _counters = psutil.net_io_counters(pernic=True)
        for ifname in _counters:
            interface = _counters[ifname]
            curr_count = [
                interface.bytes_sent,
                interface.bytes_recv,
                interface.packets_sent,
                interface.packets_recv,
                interface.errout,
                interface.errin,
            ]
            yield (ifname, curr_count)

    def get_feature(self):
        return 'interface'

    def crawl(self, container_id, avoid_setns=False, **kwargs):

        logger.debug(
            'Crawling %s for container %s' %
            (self.get_feature(), container_id))

        container = DockerContainer(container_id)

        if avoid_setns:
            raise NotImplementedError('avoidsetns mode not implemented')
        else:
            interfaces = run_as_another_namespace(
                container.pid, ['net'], self._crawl_interface_counters)

        for (ifname, curr_count) in interfaces:
            feature_key = '{0}-{1}'.format('interface', ifname)

            cache_key = '{0}-{1}-{2}'.format(container.long_id,
                                             container.pid,
                                             feature_key)

            (prev_count, prev_time) = self._cache_get_value(cache_key)
            self._cache_put_value(cache_key, curr_count)

            if prev_count and prev_time:
                d = time.time() - prev_time
                diff = [(a - b) / d for (a, b) in zip(curr_count,
                                                      prev_count)]
            else:

                # first measurement

                diff = [0] * 6

            feature_attributes = InterfaceFeature._make(diff)

            yield (feature_key, feature_attributes, 'interface')
