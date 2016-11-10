try:
    from crawler.dockercontainer import DockerContainer
    from crawler.icrawl_plugin import IContainerCrawler
    from crawler.namespace import run_as_another_namespace, ALL_NAMESPACES
    from crawler.features import LoadFeature
except ImportError:
    from dockercontainer import DockerContainer
    from icrawl_plugin import IContainerCrawler
    from namespace import run_as_another_namespace, ALL_NAMESPACES
    from features import LoadFeature

import logging
import os

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
        container = DockerContainer(container_id)
        logger.debug(
            'Crawling %s for container %s' %
            (self.get_feature(), container_id))

        if avoid_setns:
            raise NotImplementedError()
        else:  # in all other cases, including wrong mode set
            return run_as_another_namespace(container.pid,
                                            ALL_NAMESPACES,
                                            self.crawl_load)
