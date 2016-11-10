try:
    from crawler.icrawl_plugin import IHostCrawler
    from crawler.plugins.metric_crawler import crawl_metrics
except ImportError:
    from icrawl_plugin import IHostCrawler
    from plugins.metric_crawler import crawl_metrics

import logging

logger = logging.getLogger('crawlutils')


class MetricHostCrawler(IHostCrawler):

    def get_feature(self):
        return 'metric'

    def crawl(self, **kwargs):
        logger.debug('Crawling %s' % (self.get_feature()))

        return crawl_metrics()
