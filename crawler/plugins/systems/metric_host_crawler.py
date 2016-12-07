import logging

from icrawl_plugin import IHostCrawler
from utils.metric_utils import crawl_metrics

logger = logging.getLogger('crawlutils')


class MetricHostCrawler(IHostCrawler):

    def get_feature(self):
        return 'metric'

    def crawl(self, **kwargs):
        logger.debug('Crawling %s' % (self.get_feature()))

        return crawl_metrics()
