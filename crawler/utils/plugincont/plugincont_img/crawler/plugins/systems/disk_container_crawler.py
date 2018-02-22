import logging

from icrawl_plugin import IContainerCrawler
from utils.disk_utils import crawl_disk_partitions

logger = logging.getLogger('crawlutils')


class DiskContainerCrawler(IContainerCrawler):

    def get_feature(self):
        return 'disk'

    def crawl(self, container_id, avoid_setns=False, **kwargs):
        logger.debug(
            'Crawling %s for container %s' %
            (self.get_feature(), container_id))

        if avoid_setns:
            raise NotImplementedError('avoidsetns mode not implemented')
        else:  # in all other cases, including wrong mode set
            return crawl_disk_partitions()
