import logging

import psutil

from icrawl_plugin import IHostCrawler
from utils.features import MemoryFeature

logger = logging.getLogger('crawlutils')


class MemoryHostCrawler(IHostCrawler):

    def get_feature(self):
        return 'memory'

    def crawl(self, **kwargs):
        logger.debug('Crawling %s' % (self.get_feature()))

        vm = psutil.virtual_memory()

        if (vm.free + vm.used) > 0:
            util_percentage = float(vm.used) / (vm.free + vm.used) * 100.0
        else:
            util_percentage = 'unknown'

        feature_attributes = MemoryFeature(vm.used, vm.buffers, vm.cached,
                                           vm.free, util_percentage)

        return [('memory', feature_attributes, 'memory')]
