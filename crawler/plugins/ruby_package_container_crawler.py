import dockerutils
from icrawl_plugin import IContainerCrawler
from namespace import run_as_another_namespace, ALL_NAMESPACES
import logging
from misc import subprocess_run
import re
import subprocess


logger = logging.getLogger('crawlutils')


class RubyPackageCrawler(IContainerCrawler):

    def get_feature(self):
        return 'ruby-package'

    def crawl(self, container_id, **kwargs):
        inspect = dockerutils.exec_dockerinspect(container_id)
        state = inspect['State']
        pid = str(state['Pid'])
        logger.debug('Crawling OS for container %s' % container_id)

        crawl_mode = ''

        if 'crawl_mode' in kwargs:
            crawl_mode = kwargs.get('crawl_mode')

        if crawl_mode == "MOUNTPOINT":
            # TODO: return self._crawl_without_setns(container_id)
            raise NotImplementedError
        else:  # in all other cases, including wrong mode set
            return run_as_another_namespace(pid,
                                            ALL_NAMESPACES,
                                            self._crawl_in_system)

    def _crawl_in_system(self):
        proc = subprocess.Popen(['which', 'gem'], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        output, err = proc.communicate()
        if output:
            output = subprocess_run(['gem', 'list'], shell=False)
            pkg_list = output.strip('\n')
            if pkg_list:
                for pkg in pkg_list.split('\n'):
                    pkg_name = pkg.split()[0]
                    pkg_version = re.findall(r'[\d\.]+', pkg)[0]
                    yield (
                        pkg_name,
                        {"pkgname": pkg_name, "pkgversion": pkg_version},
                        'ruby-package')

    def _crawl_without_setns(self, container_id):
        return []
