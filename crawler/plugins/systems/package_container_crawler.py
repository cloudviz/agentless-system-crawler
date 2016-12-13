import logging

from icrawl_plugin import IContainerCrawler
from utils.crawler_exceptions import CrawlError
from utils.dockerutils import (exec_dockerinspect,
                               get_docker_container_rootfs_path)
from utils.misc import join_abs_paths
from utils.namespace import run_as_another_namespace, ALL_NAMESPACES
from utils.package_utils import crawl_packages

logger = logging.getLogger('crawlutils')


class PackageContainerCrawler(IContainerCrawler):

    def get_feature(self):
        return 'package'

    def crawl(self, container_id=None, avoid_setns=False,
              root_dir='/', **kwargs):
        logger.debug('Crawling packages for container %s' % container_id)
        inspect = exec_dockerinspect(container_id)
        state = inspect['State']
        pid = str(state['Pid'])

        if avoid_setns:
            rootfs_dir = get_docker_container_rootfs_path(
                container_id)
            return crawl_packages(
                root_dir=join_abs_paths(rootfs_dir, root_dir),
                reload_needed=True)
        else:  # in all other cases, including wrong mode set
            try:
                return run_as_another_namespace(pid,
                                                ALL_NAMESPACES,
                                                crawl_packages,
                                                None,
                                                root_dir, 0, False)
            except CrawlError:

                # Retry the crawl avoiding the setns() syscall. This is
                # needed for PPC where we can not jump into the container and
                # run its apt or rpm commands.

                rootfs_dir = get_docker_container_rootfs_path(
                    container_id)
                return crawl_packages(
                    root_dir=join_abs_paths(rootfs_dir, root_dir),
                    reload_needed=True)
