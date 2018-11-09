import logging
import re
import subprocess
import os
import utils.dockerutils

from icrawl_plugin import IContainerCrawler
from utils.namespace import run_as_another_namespace, ALL_NAMESPACES

logger = logging.getLogger('crawlutils')


class NodePackageCrawler(IContainerCrawler):

    def get_feature(self):
        return 'node-package'

    def parse_packages(self, output):
        if not output:
            return

        pkg_list = output.strip('\n')
        if not pkg_list:
            return

        for pkg in pkg_list.split('\n'):
            if 'deduped' in pkg.split():
                continue
            pkg_info = re.findall(r"\S*@\S*", pkg)
            for _pkg_info in pkg_info:
                pkg_name, pkg_version = _pkg_info.split('@')
                yield (
                    pkg_name,
                    {"pkgname": pkg_name, "pkgversion": pkg_version},
                    'node-package')

    def get_packages_by_cmd(self, location):
        if location == 'global':
            cmd = 'npm list -g'
        else:
            os.chdir(location)
            cmd = 'npm list'

        proc = subprocess.Popen(
            ['sh', '-c', cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        output, err = proc.communicate()

        return list(self.parse_packages(output))

    def walk_fs_node_modules(self, path):
        output = []
        if os.path.isdir(path):
            for (root_dir, dirs, files) in os.walk(path):
                if 'package.json' in files and 'node_modules' not in root_dir:
                    output += [root_dir]
        return output

    def get_node_modules_location(self):
        # npm list -g will list system/global modules
        # But for an app's/project's local packages need to hunt for
        # package.json file or node-modules/ dir
        candidate_paths = ["/home/"]
        node_modules_location = []
        for path in candidate_paths:
            node_modules_location += self.walk_fs_node_modules(path)
        return node_modules_location

    def crawl_in_system(self):
        packages = self.get_packages_by_cmd('global')
        node_modules_location = self.get_node_modules_location()
        for location in node_modules_location:
            packages += self.get_packages_by_cmd(location)
        return packages

    def crawl(self, container_id, avoid_setns=False, **kwargs):
        inspect = utils.dockerutils.exec_dockerinspect(container_id)
        state = inspect['State']
        pid = str(state['Pid'])
        logger.debug('Crawling OS for container %s' % container_id)

        if avoid_setns:
            raise NotImplementedError()
        else:
            return run_as_another_namespace(pid,
                                            ALL_NAMESPACES,
                                            self.crawl_in_system)
