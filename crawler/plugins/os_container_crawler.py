import dockerutils
from icrawl_plugin import IContainerCrawler
from namespace import run_as_another_namespace, ALL_NAMESPACES
from plugins.os_crawler import crawl_os, crawl_os_mountpoint
import logging

logger = logging.getLogger('crawlutils')


class OSContainerCrawler(IContainerCrawler):

    def get_feature(self):
        return 'os'

    def crawl(self, container_id, avoid_setns=False, **kwargs):
        inspect = dockerutils.exec_dockerinspect(container_id)
        state = inspect['State']
        pid = str(state['Pid'])
        logger.debug('Crawling OS for container %s' % container_id)

        if avoid_setns:
            mp = dockerutils.get_docker_container_rootfs_path(container_id)
            return crawl_os_mountpoint(mp)
        else:  # in all other cases, including wrong mode set
            return run_as_another_namespace(pid,
                                            ALL_NAMESPACES,
                                            crawl_os)
