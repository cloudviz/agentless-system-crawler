import logging

try:
    from crawler.package_crawler import crawl_packages
    from crawler.runtime_environment import IRuntimeEnvironment
    from crawler.dockerutils import (exec_dockerinspect,
                                     get_docker_container_rootfs_path)
    from crawler.namespace import run_as_another_namespace, ALL_NAMESPACES
    from crawler.misc import join_abs_paths
    from crawler.crawler_exceptions import (CrawlError,
                                            CrawlUnsupportedPackageManager)
    from crawler.icrawl_plugin import IContainerCrawler
except ImportError:
    from package_crawler import crawl_packages
    from runtime_environment import IRuntimeEnvironment
    from dockerutils import (exec_dockerinspect,
                             get_docker_container_rootfs_path)
    from namespace import run_as_another_namespace, ALL_NAMESPACES
    from misc import join_abs_paths
    from crawler_exceptions import (CrawlError,
                                    CrawlUnsupportedPackageManager)
    from icrawl_plugin import IContainerCrawler

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
