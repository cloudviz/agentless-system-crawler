import logging
import os
import re
import subprocess

import utils.dockerutils

from icrawl_plugin import IContainerCrawler

logger = logging.getLogger('crawlutils')


class PythonPackageCrawler(IContainerCrawler):

    def get_feature(self):
        return 'pythonpackage'

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
                    'pythonpackage')

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
                    'pythonpackage')

    def _crawl_without_setns(self, container_id):
        return self._get_packages_by_extension('/rootfs_local')

    def _crawl_in_system(self):
        real_root = os.open('/', os.O_RDONLY)
        os.chroot('/rootfs_local')

        if self.get_packages_generic is True:
            mountpoint = '/'
            pkg_list = list(self._get_packages_by_extension(mountpoint))
        else:
            pkg_list = list(self._get_packages_by_cmd())

        os.fchdir(real_root)
        os.chroot('.')
        return pkg_list

    def crawl(self, container_id, avoid_setns=False, **kwargs):

        if avoid_setns:
            return self._crawl_without_setns(container_id)
        else:  # in all other cases, including wrong mode set
            self.get_packages_generic = True  # can be made an arg to crawl()
            return self._crawl_in_system()
