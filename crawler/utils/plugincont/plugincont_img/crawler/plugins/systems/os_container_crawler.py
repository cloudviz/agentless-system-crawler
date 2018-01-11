import logging
import os
import utils.dockerutils
from icrawl_plugin import IContainerCrawler
from utils.namespace import run_as_another_namespace, ALL_NAMESPACES
from utils.os_utils import crawl_os, crawl_os_mountpoint

logger = logging.getLogger('crawlutils')


class OSContainerCrawler(IContainerCrawler):

    def get_feature(self):
        return 'os'

    def crawl(self, container_id, avoid_setns=False, **kwargs):
        logger.debug('Crawling OS for container %s' % container_id)

        if avoid_setns:
            return crawl_os_mountpoint('/rootfs_local')
        else:  # in all other cases, including wrong mode set
            real_root = os.open('/', os.O_RDONLY)
            os.chroot('/rootfs_local')
            os.chdir('/')
            os_info = crawl_os() 
            os.fchdir(real_root)
            os.chroot('.')
            return os_info
