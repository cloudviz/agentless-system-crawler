import logging

from icrawl_plugin import IContainerCrawler
from utils.connection_utils import crawl_connections

logger = logging.getLogger('crawlutils')


class ConnectionContainerCrawler(IContainerCrawler):

    def get_feature(self):
        return 'connection'

    def crawl(self, container_id, avoid_setns=False, **kwargs):
        logger.debug(
            'Crawling %s for container %s' %
            (self.get_feature(), container_id))

        if avoid_setns:
            raise NotImplementedError('avoidsetns mode not implemented')
        else:  # in all other cases, including wrong mode set
            return crawl_connections()
