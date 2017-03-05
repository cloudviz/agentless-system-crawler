import logging

from icrawl_plugin import IHostCrawler
from utils.config_utils import crawl_config_files

logger = logging.getLogger('crawlutils')


class ConfigHostCrawler(IHostCrawler):

    def get_feature(self):
        return 'config'

    def crawl(
            self,
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
            target_config_files=[],
            **kwargs):
        return crawl_config_files(
            root_dir=root_dir,
            exclude_dirs=exclude_dirs,
            known_config_files=known_config_files,
            discover_config_files=discover_config_files,
            target_config_files=target_config_files)
