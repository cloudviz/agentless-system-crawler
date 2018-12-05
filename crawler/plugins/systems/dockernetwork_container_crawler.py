from utils.dockerutils import exec_dockernetwork
from icrawl_plugin import IContainerCrawler

import logging

logger = logging.getLogger('crawlutils')


class DockernetworkContainerCrawler(IContainerCrawler):

    def get_feature(self):
        return 'dockernetwork'

    def crawl(self, container_id, avoid_setns=False, **kwargs):
        network = exec_dockernetwork(container_id)
        yield (container_id, network, 'dockernetwork')
