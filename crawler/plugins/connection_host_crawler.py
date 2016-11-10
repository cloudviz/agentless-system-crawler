try:
    from crawler.icrawl_plugin import IHostCrawler
    from crawler.plugins.connection_crawler import crawl_connections
except ImportError:
    from icrawl_plugin import IHostCrawler
    from plugins.connection_crawler import crawl_connections

import logging

logger = logging.getLogger('crawlutils')


class ConnectionHostCrawler(IHostCrawler):

    def get_feature(self):
        return 'connection'

    def crawl(self, **kwargs):
        logger.debug('Crawling %s' % (self.get_feature()))

        return crawl_connections()
