import logging

from icrawl_plugin import IHostCrawler
from utils.connection_utils import crawl_connections

logger = logging.getLogger('crawlutils')


class ConnectionHostCrawler(IHostCrawler):

    def get_feature(self):
        return 'connection'

    def crawl(self, **kwargs):
        logger.debug('Crawling %s' % (self.get_feature()))

        return crawl_connections()
