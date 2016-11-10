try:
    from crawler.icrawl_plugin import IVMCrawler
    from crawler.features import InterfaceFeature
except ImportError:
    from icrawl_plugin import IVMCrawler
    from features import InterfaceFeature

import logging
import time

try:
    import psvmi
except ImportError:
    psvmi = None


logger = logging.getLogger('crawlutils')


class InterfaceVmCrawler(IVMCrawler):

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

    def _crawl_interface_counters(self, vm_context):
        for interface in psvmi.interface_iter(vm_context):
            curr_count = [
                interface.bytes_sent,
                interface.bytes_recv,
                interface.packets_sent,
                interface.packets_recv,
                interface.errout,
                interface.errin,
            ]
            yield (interface.ifname, curr_count)

    def get_feature(self):
        return 'interface'

    def crawl(self, vm_desc, **kwargs):

        logger.debug('Crawling %s' % self.get_feature())

        if psvmi is None:
            raise NotImplementedError()
        else:
            (domain_name, kernel_version, distro, arch) = vm_desc
            # XXX: this has to be read from some cache instead of
            # instead of once per plugin/feature
            vm_context = psvmi.context_init(
                domain_name, domain_name, kernel_version, distro, arch)
            interfaces = self._crawl_interface_counters(vm_context)

        for (interface_name, curr_count) in interfaces:
            feature_key = '{0}-{1}'.format('interface', interface_name)
            cache_key = '{0}-{1}'.format('OUTVM', feature_key)

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
