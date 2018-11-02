import logging
import re
import subprocess

import utils.dockerutils

from icrawl_plugin import IContainerCrawler
from utils.namespace import run_as_another_namespace, ALL_NAMESPACES

logger = logging.getLogger('crawlutils')


class NodePackageCrawler(IContainerCrawler):

    def get_feature(self):
        return 'node-package'

    def _get_packages_by_cmd(self):
        proc = subprocess.Popen(
            ['sh', '-c', 'npm list -g'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        output, err = proc.communicate()

        if output:
            pkg_list = output.strip('\n')
            if pkg_list:
                for pkg in pkg_list.split('\n'):
                    if pkg.split()[-1] == 'deduped':
                        continue
                    pkg_info = re.findall(r"\S*@\S*", pkg)
                    for _pkg_info in pkg_info:
                        pkg_name, pkg_version = _pkg_info.split('@')
                        yield (
                            pkg_name,
                            {"pkgname": pkg_name, "pkgversion": pkg_version},
                            'node-package')

    def _crawl_in_system(self):
        return self._get_packages_by_cmd()

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
                                            self._crawl_in_system)
