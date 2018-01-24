from __future__ import print_function
from __future__ import absolute_import
import argparse
import os

from .base_crawler import BaseCrawler
from .worker import Worker
from .containers import get_containers
from .utils import misc


class DockerContainersLogsLinker(BaseCrawler):
    """
    Class used to maintain symlinks to container log files. The idea with this
    is to symlink all log files of interest (from all containers of interest)
    to some known directory in the host. Then point some log collector like
    logstash to it (and get container logs).
    """

    def __init__(self,
                 environment='cloudsight',
                 user_list='ALL',
                 host_namespace=''):
        self.containers_list = set()
        self.new = set()
        self.deleted = set()
        self.environment = environment
        self.host_namespace = host_namespace
        self.user_list = user_list

    def update_containers_list(self):
        """
        Actually poll for new containers. This updates the list of new and
        deleted containers, in self.new and self.deleted.
        :return: None
        """
        curr_containers = set(
            get_containers(
                environment=self.environment,
                user_list=self.user_list,
                host_namespace=self.host_namespace))
        self.new = curr_containers - self.containers_list
        self.deleted = self.containers_list - curr_containers
        self.containers_list = curr_containers

    def link_containers(self):
        for container in self.deleted:
            container.unlink_logfiles()
        for container in self.new:
            container.link_logfiles()

    def crawl(self):
        self.update_containers_list()
        self.link_containers()
        return []


if __name__ == '__main__':

    euid = os.geteuid()
    if euid != 0:
        print('Need to run this as root.')
        exit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--namespace',
        dest='namespace',
        type=str,
        nargs='?',
        default=misc.get_host_ipaddr(),
        help='Data source this crawler is associated with. Defaults to '
             '/localhost',
    )
    parser.add_argument(
        '--frequency',
        dest='frequency',
        type=int,
        default=-1,
        help='Target time period for iterations. Defaults to -1 which '
             'means only run one iteration.'
    )
    parser.add_argument('--logfile', dest='logfile', type=str,
                        default='crawler.log',
                        help='Logfile path. Defaults to crawler.log'
                        )
    parser.add_argument(
        '--crawlContainers',
        dest='crawlContainers',
        type=str,
        nargs='?',
        default='ALL',
        help='List of containers to crawl as a list of Docker container IDs. '
             'If this is not passed, then just the host is crawled. '
             'Alternatively the word "ALL" can be used to crawl every '
             'container. "ALL" will crawl all namespaces including the host '
             'itself. This option is only valid for INVM crawl mode. Example: '
             '--crawlContainers 5f3380d2319e,681be3e32661',
    )
    parser.add_argument(
        '--environment',
        dest='environment',
        type=str,
        default='cloudsight',
        help='This speficies some environment specific behavior, like how '
             'to name a container. The way to add a new behavior is by '
             'implementing a plugin (see plugins/cloudsight_environment.py '
             'as an example. Defaults to "cloudsight".',
    )

    misc.setup_logger('crawlutils', 'linker.log')
    misc.setup_logger('yapsy', 'yapsy.log')
    args = parser.parse_args()
    crawler = DockerContainersLogsLinker(environment=args.environment,
                                         user_list=args.crawlContainers,
                                         host_namespace=args.namespace)

    worker = Worker(emitters=None,
                    frequency=args.frequency,
                    crawler=crawler)

    try:
        worker.run()
    except KeyboardInterrupt:
        pass
