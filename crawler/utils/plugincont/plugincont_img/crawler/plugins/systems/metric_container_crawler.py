import logging

from icrawl_plugin import IContainerCrawler
from utils.metric_utils import crawl_metrics

logger = logging.getLogger('crawlutils')


class MetricContainerCrawler(IContainerCrawler):

    def get_feature(self):
        return 'metric'

    def crawl(self, container_id, avoid_setns=False, **kwargs):
        logger.debug(
            'Crawling %s for container %s' %
            (self.get_feature(), container_id))

        if avoid_setns:
            raise NotImplementedError('avoidsetns mode not implemented')
        else:  # in all other cases, including wrong mode set
            return list(crawl_metrics()) 
