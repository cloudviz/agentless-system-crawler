import logging
import os

from icrawl_plugin import IContainerCrawler
from utils.features import LoadFeature

logger = logging.getLogger('crawlutils')


class LoadContainerCrawler(IContainerCrawler):

    def get_feature(self):
        return 'load'

    def crawl_load(self):
        load = os.getloadavg()
        feature_key = 'load'
        feature_attributes = LoadFeature(load[0], load[1], load[1])
        yield (feature_key, feature_attributes, 'load')

    def crawl(self, container_id, avoid_setns=False, **kwargs):
        logger.debug(
            'Crawling %s for container %s' %
            (self.get_feature(), container_id))

        if avoid_setns:
            raise NotImplementedError()
        else:  # in all other cases, including wrong mode set
            return self.crawl_load()
