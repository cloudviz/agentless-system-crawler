from utils.dockerutils import exec_dockerinspect
from icrawl_plugin import IContainerCrawler

import logging

logger = logging.getLogger('crawlutils')


class DockerinspectContainerCrawler(IContainerCrawler):

    def get_feature(self):
        return 'dockerinspect'

    def crawl(self, container_id, avoid_setns=False, **kwargs):
        inspect = exec_dockerinspect(container_id)
        yield (container_id, inspect, 'dockerinspect')
