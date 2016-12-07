import logging
import os
import re
import subprocess

import dockerutils

from icrawl_plugin import IContainerCrawler
from utils.namespace import run_as_another_namespace, ALL_NAMESPACES

logger = logging.getLogger('crawlutils')


class PythonPackageCrawler(IContainerCrawler):

    def get_feature(self):
        return 'python-package'

    def _crawl_files(self, path, extensions):
        output = []
        if os.path.isdir(path):
            for (root_dirpath, dirs, files) in os.walk(path):
                output += [
                    f for ext in extensions for f in files if f.endswith(ext)]
                output += [
                    d for ext in extensions for d in dirs if d.endswith(ext)]
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
            packages += self._crawl_files(path, ['.egg-info', '.dist-info'])

        for pkg in packages:
            pkg_name = None
            name_parts = re.match(
                r'(.*)-([\d\.]*)(\.egg-info|\.dist-info)', pkg)
            if name_parts is not None:
                pkg_name = name_parts.group(1)
                pkg_version = name_parts.group(2)
            else:
                name_parts = re.match(r'(.*)(\.egg-info|\.dist-info)', pkg)
                if name_parts is not None:
                    pkg_name = name_parts.group(1)
                    pkg_version = 'unknown'
                    # TODO: get version from 'Version:' field in such files
                    # ex: /usr/lib/python2.7/argparse.egg-info: Version: 1.2.1
            if pkg_name is not None:
                yield (
                    pkg_name,
                    {"pkgname": pkg_name, "pkgversion": pkg_version},
                    'python-package')

    def _get_packages_by_cmd(self):
        # better coverage with pkg_resources.working_set than
        # pip list, pip freeze, pip.get_installed_distributions()
        # but following throws child exception from
        # namespace.py:run_as_another_namespace()
        # with  ERROR string index out of range
        # but works fine in a standalalone python file:
        # ['python', '-c', 'import pkg_resources; pkgs =
        #   [ (p.key, p.version) for p in pkg_resources.working_set];
        #       print pkgs'],

        proc = subprocess.Popen(
            ['sh', '-c', ' export LC_ALL=C; pip list'],
            # othewrwise pip says locale.Error: unsupported locale setting
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        output, err = proc.communicate()

        if output:
            pkg_list = output.strip('\n')
            for pkg in pkg_list.split('\n'):
                pkg_name = pkg.split()[0]
                pkg_version = pkg.split()[1][1:-1]
                yield (
                    pkg_name,
                    {"pkgname": pkg_name, "pkgversion": pkg_version},
                    'python-package')

    def _crawl_without_setns(self, container_id):
        mountpoint = dockerutils.get_docker_container_rootfs_path(container_id)
        return self._get_packages_by_extension(mountpoint)

    def _crawl_in_system(self):
        if self.get_packages_generic is True:
            mountpoint = '/'
            return self._get_packages_by_extension(mountpoint)
        else:
            return self._get_packages_by_cmd()

    def crawl(self, container_id, avoid_setns=False, **kwargs):
        inspect = dockerutils.exec_dockerinspect(container_id)
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
