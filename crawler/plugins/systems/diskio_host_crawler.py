import logging
import time
import psutil

from icrawl_plugin import IHostCrawler
from utils.features import DiskioFeature

logger = logging.getLogger('crawlutils')


class DiskioHostCrawler(IHostCrawler):
    '''
    Plugin for crawling disk I/O counters from host and
    computing the bytes/second rate for read and write operations
    '''

    def __init__(self):
        self._cached_values = {}
        self._previous_rates = {}

    def _cache_put_value(self, key, value):
        self._cached_values[key] = (value, time.time())

    def _cache_get_value(self, key):
        if key in self._cached_values:
            return self._cached_values[key]
        else:
            return None, None

    def _crawl_disk_io_counters(self):
        try:
            disk_counters = psutil.disk_io_counters(perdisk=True)
            for device_name in disk_counters:
                counters = disk_counters[device_name]
                curr_counters = [
                    counters.read_count,
                    counters.write_count,
                    counters.read_bytes,
                    counters.write_bytes
                ]
                logger.debug(
                    u'Disk I/O counters - {0}: {1}'.format(device_name,
                                                           curr_counters))
                yield (device_name, curr_counters)
        except OSError as e:
            logger.debug(
                u'Caught exception when crawling disk I/O counters: {0}'.
                format(e))

    def crawl(self, **kwargs):
        logger.debug('Crawling %s' % self.get_feature())
        diskio_data = self._crawl_disk_io_counters()
        for device_name, curr_counters in diskio_data:
            logger.debug(u'Processing device {0}; counters = {1}'.
                         format(device_name, curr_counters))

            feature_key = '{0}-{1}'.format('diskio', device_name)
            cache_key = '{0}-{1}'.format('INVM', feature_key)
            (prev_counters, prev_time) = self._cache_get_value(cache_key)
            self._cache_put_value(cache_key, curr_counters)

            if prev_counters and prev_time:
                # Compute the rates (per second) for each attribute, namely:
                #   read_op/s, write_op/s, read_bytes/s, and write_bytes/s
                time_diff = time.time() - prev_time
                rates = [
                    round(
                        (a - b) / time_diff,
                        2) for (
                        a,
                        b) in zip(
                        curr_counters,
                        prev_counters)]
                for i in range(len(rates)):
                    if rates[i] < 0:
                        # The corresponding OS counter has wrapped
                        # For now, let's return the previous measurement
                        # to avoid a huge drop on the metric graph
                        rates[i] = self._previous_rates[device_name][i]
                        logger.debug(
                            u'Counter "{0}" for device {1} has wrapped'.
                            format(i, device_name))
            else:
                # first measurement
                rates = [0] * 4

            self._previous_rates[device_name] = rates
            logger.debug(
                u'Disk I/O counters rates- {0}: {1}'.format(device_name,
                                                            rates))

            diskio_feature_attributes = DiskioFeature._make(rates)
            yield(feature_key, diskio_feature_attributes, 'diskio')

    def get_feature(self):
        return 'diskio'
