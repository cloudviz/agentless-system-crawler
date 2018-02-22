import logging
import os

from icrawl_plugin import IContainerCrawler
from utils.crawler_exceptions import CrawlError
from utils.misc import join_abs_paths
from utils.package_utils import crawl_packages

logger = logging.getLogger('crawlutils')


class PackageContainerCrawler(IContainerCrawler):

    def get_feature(self):
        return 'package'

    def crawl(self, container_id=None, avoid_setns=False,
              root_dir='/', **kwargs):
        logger.debug('Crawling packages for container %s' % container_id)

        if avoid_setns:
            rootfs_dir = '/rootfs_local'
            return crawl_packages(
                root_dir=join_abs_paths(rootfs_dir, root_dir),
                reload_needed=True)
        else:  # in all other cases, including wrong mode set
            try:
                print "in package plugin" 
                real_root = os.open('/', os.O_RDONLY)
                os.chroot('/rootfs_local')
                os.chdir('/')
                pkg_list = list(crawl_packages(None, root_dir, 0, False))
                os.fchdir(real_root)
                os.chroot('.')
                return pkg_list
            except CrawlError:

                # Retry the crawl avoiding the setns() syscall. This is
                # needed for PPC where we can not jump into the container and
                # run its apt or rpm commands.
           
                print "Got CrawlError in package plugin" 
                rootfs_dir = '/rootfs_local'
                return crawl_packages(
                    root_dir=join_abs_paths(rootfs_dir, root_dir),
                    reload_needed=True)
