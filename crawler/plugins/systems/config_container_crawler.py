import logging

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
                "/etc/my.cnf",
                "/etc/mysql/my.cnf",
                "/etc/nginx/nginx.conf",
                "/etc/init/ssh.conf",
                "/etc/apache2/apache.conf",
                "/etc/apache2/mods-available/ssl.conf",
                "/etc/apache2/ports.conf",
                "/etc/apache2/sites-enabled/000-default.conf",
                "/etc/httpd/conf.d/ssl.conf",
                "/etc/httpd/conf/httpd.conf",
                "/etc/httpd/httpd.conf",
                "/etc/sysctl.conf",
                '/etc/sudoers'],
            discover_config_files=False,
            **kwargs):
        inspect = utils.dockerutils.exec_dockerinspect(container_id)
        state = inspect['State']
        pid = str(state['Pid'])
        logger.debug('Crawling config for container %s' % container_id)

        if avoid_setns:
            rootfs_dir = utils.dockerutils.get_docker_container_rootfs_path(
                container_id)
            exclude_dirs = [utils.misc.join_abs_paths(rootfs_dir, d)
                            for d in exclude_dirs]
            return crawl_config_files(
                root_dir=utils.misc.join_abs_paths(rootfs_dir, root_dir),
                exclude_dirs=exclude_dirs,
                root_dir_alias=root_dir,
                known_config_files=known_config_files,
                discover_config_files=discover_config_files)
        else:  # in all other cases, including wrong mode set
            return run_as_another_namespace(pid,
                                            ['mnt'],
                                            crawl_config_files,
                                            root_dir,
                                            exclude_dirs,
                                            None,
                                            known_config_files,
                                            discover_config_files)
