import logging
import os
import utils.dockerutils
import utils.misc
from icrawl_plugin import IContainerCrawler
from utils.config_utils import crawl_config_files
from utils.namespace import run_as_another_namespace

logger = logging.getLogger('crawlutils')


class ConfigContainerCrawler(IContainerCrawler):

    def get_feature(self):
        return 'config'

    def crawl(
            self,
            container_id=None,
            avoid_setns=False,
            root_dir='/',
            exclude_dirs=[
                '/dev',
                '/proc',
                '/mnt',
                '/tmp',
                '/var/cache',
                '/usr/share/man',
                '/usr/share/doc',
                '/usr/share/mime'],
            known_config_files=[
                '/etc/passwd',
                '/etc/group',
                '/etc/hosts',
                '/etc/hostname',
                '/etc/mtab',
                '/etc/fstab',
                '/etc/aliases',
                '/etc/ssh/ssh_config',
                '/etc/ssh/sshd_config',
                '/etc/sudoers'],
            discover_config_files=False,
            **kwargs):
        logger.debug('Crawling config for container %s' % container_id)

        if avoid_setns:
            rootfs_dir = '/rootfs_local'
            exclude_dirs = [utils.misc.join_abs_paths(rootfs_dir, d)
                            for d in exclude_dirs]
            return list(crawl_config_files(
                root_dir=utils.misc.join_abs_paths(rootfs_dir, root_dir),
                exclude_dirs=exclude_dirs,
                root_dir_alias=root_dir,
                known_config_files=known_config_files,
                discover_config_files=discover_config_files))
        else:  # in all other cases, including wrong mode set
            real_root = os.open('/', os.O_RDONLY)
            os.chroot('/rootfs_local')
            config_list = list(crawl_config_files( root_dir,
                                            exclude_dirs,
                                            None,
                                            known_config_files,
                                            discover_config_files))
            os.fchdir(real_root)
            os.chroot('.')
            return config_list
