from utils.dockerutils import exec_docker_history
from icrawl_plugin import IContainerCrawler

import logging

logger = logging.getLogger('crawlutils')


class DockerhistoryContainerCrawler(IContainerCrawler):

    def get_feature(self):
        return 'dockerhistory'

    def crawl(self, container_id, avoid_setns=False, **kwargs):
        history = exec_docker_history(container_id)
        image_id = history[0]['Id']
        yield (image_id, {'history': history}, 'dockerhistory')
