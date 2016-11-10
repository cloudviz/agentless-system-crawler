try:
    from crawler.icrawl_plugin import IHostCrawler
    from crawler.features import LoadFeature
except ImportError:
    from icrawl_plugin import IHostCrawler
    from features import LoadFeature

import logging
import os

logger = logging.getLogger('crawlutils')


class LoadHostCrawler(IHostCrawler):

    def get_feature(self):
        return 'load'

    def crawl_load(self):
        load = os.getloadavg()
        feature_key = 'load'
        feature_attributes = LoadFeature(load[0], load[1], load[1])
        yield (feature_key, feature_attributes, 'load')

    def crawl(self, **kwargs):
        logger.debug('Crawling %s' % (self.get_feature()))

        return self.crawl_load()
