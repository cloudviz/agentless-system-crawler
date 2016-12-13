import logging

import utils.dockerutils
from icrawl_plugin import IContainerCrawler
from utils.namespace import run_as_another_namespace, ALL_NAMESPACES
from utils.os_utils import crawl_os, crawl_os_mountpoint

logger = logging.getLogger('crawlutils')


class OSContainerCrawler(IContainerCrawler):

    def get_feature(self):
        return 'os'

    def crawl(self, container_id, avoid_setns=False, **kwargs):
        inspect = utils.dockerutils.exec_dockerinspect(container_id)
        state = inspect['State']
        pid = str(state['Pid'])
        logger.debug('Crawling OS for container %s' % container_id)

        if avoid_setns:
            mp = utils.dockerutils.get_docker_container_rootfs_path(
                container_id)
            return crawl_os_mountpoint(mp)
        else:  # in all other cases, including wrong mode set
            return run_as_another_namespace(pid,
                                            ALL_NAMESPACES,
                                            crawl_os)
