try:
    from crawler.icrawl_plugin import IHostCrawler
    from crawler.plugins.disk_crawler import crawl_disk_partitions
except ImportError:
    from icrawl_plugin import IHostCrawler
    from plugins.disk_crawler import crawl_disk_partitions

import logging

logger = logging.getLogger('crawlutils')


class DiskHostCrawler(IHostCrawler):

    def get_feature(self):
        return 'disk'

    def crawl(self, **kwargs):
        logger.debug('Crawling %s' % (self.get_feature()))

        return crawl_disk_partitions()
