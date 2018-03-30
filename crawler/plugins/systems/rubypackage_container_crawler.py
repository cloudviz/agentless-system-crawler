import logging
import os
import re
import subprocess

import utils.dockerutils

from icrawl_plugin import IContainerCrawler
from utils.namespace import run_as_another_namespace, ALL_NAMESPACES

logger = logging.getLogger('crawlutils')


class RubyPackageCrawler(IContainerCrawler):

    def get_feature(self):
        return 'rubypackage'

    def _crawl_files(self, path, extension):
        output = []
        if os.path.isdir(path):
            for (root_dirpath, dirs, files) in os.walk(path):
                output += [f for f in files if f.endswith(extension)]
        return output

    def _get_packages_by_extension(self, mountpoint):
        candidate_paths = [
            "usr/lib/",
            "usr/share/",
            "usr/local/lib/",
            "usr/local/share/",
            "usr/local/bundle/",
            "var/lib/"]

        packages = []

        for path in candidate_paths:
            path = os.path.join(mountpoint, path)
            packages += self._crawl_files(path, ".gemspec")

        for pkg in packages:
            name_parts = re.match(r'(.*)-([\d\.]*)(\.gemspec)', pkg)
            if name_parts is not None:
                pkg_name = name_parts.group(1)
                pkg_version = name_parts.group(2)
                yield (
                    pkg_name,
                    {"pkgname": pkg_name, "pkgversion": pkg_version},
                    'rubypackage')

    def _get_packages_by_cmd(self):
        proc = subprocess.Popen(
            ['sh', '-c', 'gem list'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        output, err = proc.communicate()

        if output:
            pkg_list = output.strip('\n')
            if pkg_list:
                for pkg in pkg_list.split('\n'):
                    pkg_name = pkg.split()[0]
                    pkg_versions = re.findall(r'[\d\.]+', pkg)
                    for pkg_version in pkg_versions:
                        yield (
                            pkg_name,
                            {"pkgname": pkg_name, "pkgversion": pkg_version},
                            'rubypackage')

    def _crawl_without_setns(self, container_id):
        mountpoint = utils.dockerutils.get_docker_container_rootfs_path(
            container_id)
        return self._get_packages_by_extension(mountpoint)

    def _crawl_in_system(self):
        if self.get_packages_generic is True:
            mountpoint = '/'
            return self._get_packages_by_extension(mountpoint)
        else:
            return self._get_packages_by_cmd()

    def crawl(self, container_id, avoid_setns=False, **kwargs):
        inspect = utils.dockerutils.exec_dockerinspect(container_id)
        state = inspect['State']
        pid = str(state['Pid'])
        logger.debug('Crawling OS for container %s' % container_id)

        if avoid_setns:
            return self._crawl_without_setns(container_id)
        else:  # in all other cases, including wrong mode set
            self.get_packages_generic = False  # can be made an arg to crawl()
            return run_as_another_namespace(pid,
                                            ALL_NAMESPACES,
                                            self._crawl_in_system)
