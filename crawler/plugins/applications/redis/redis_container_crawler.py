from icrawl_plugin import IContainerCrawler
from plugins.applications.redis import feature
from plugins.applications.util import ContainerInspector
from requests.exceptions import ConnectionError
import redis
import logging

logger = logging.getLogger('crawlutils')


class RedisContainerCrawler(IContainerCrawler):
    '''
    Crawling app provided metrics for redis container on docker.
    Usually redis listens on port 6379.

    ContainerInspector class automatically searches
    IP and port for the container.
    If not set, the it tries to access default port.
    '''

    feature_type = "application"
    feature_key = "redis"
    default_port = 6379

    def get_feature(self):
        return self.feature_type

    def crawl(self, container_id=None, **kwargs):

        # only crawl redis container. Otherwise, quit.
        c = ContainerInspector(container_id)
        if not c.is_app_container(self.feature_key):
            return

        # extract IP and Port information
        ip = c.get_ip()
        ports = c.get_ports()

        # set default port number
        if len(ports) == 0:
            ports.append(self.default_port)

        # querying all available ports
        for port in ports:
            client = redis.Redis(host=ip, port=port)
            try:
                metrics = client.info()
            except ConnectionError:
                logger.info("redis does not listen on port:%d", port)
                continue
            feature_attributes = feature.create_feature(metrics)
            return [(self.feature_key, feature_attributes, self.feature_type)]
