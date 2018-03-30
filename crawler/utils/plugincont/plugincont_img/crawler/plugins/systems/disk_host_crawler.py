import logging

from icrawl_plugin import IHostCrawler
from utils.disk_utils import crawl_disk_partitions

logger = logging.getLogger('crawlutils')


class DiskHostCrawler(IHostCrawler):

    def get_feature(self):
        return 'disk'

    def crawl(self, **kwargs):
        logger.debug('Crawling %s' % (self.get_feature()))

        return crawl_disk_partitions()
