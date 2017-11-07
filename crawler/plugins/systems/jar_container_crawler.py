import logging

import utils.dockerutils
import utils.misc
from icrawl_plugin import IContainerCrawler
from utils.jar_utils import crawl_jar_files
from utils.namespace import run_as_another_namespace

logger = logging.getLogger('crawlutils')


class JarContainerCrawler(IContainerCrawler):

    def get_feature(self):
        return 'jar'

    def crawl(
            self,
            container_id=None,
            avoid_setns=False,
            root_dir='/',
            exclude_dirs=[
                '/boot',
                '/dev',
                '/proc',
                '/sys',
                '/mnt',
                '/tmp',
                '/var/cache',
                '/usr/share/man',
                '/usr/share/doc',
                '/usr/share/mime'],
            **kwargs):
        inspect = utils.dockerutils.exec_dockerinspect(container_id)
        state = inspect['State']
        pid = str(state['Pid'])
        logger.debug('Crawling jars for container %s' % container_id)

        if avoid_setns:
            rootfs_dir = utils.dockerutils.get_docker_container_rootfs_path(
                container_id)
            exclude_dirs = [utils.misc.join_abs_paths(rootfs_dir, d)
                            for d in exclude_dirs]
            return crawl_jar_files(
                root_dir=utils.misc.join_abs_paths(rootfs_dir, root_dir),
                exclude_dirs=exclude_dirs,
                root_dir_alias=root_dir)
        else:  # in all other cases, including wrong mode set
            return run_as_another_namespace(pid,
                                            ['mnt'],
                                            crawl_jar_files,
                                            root_dir,
                                            exclude_dirs,
                                            None)
