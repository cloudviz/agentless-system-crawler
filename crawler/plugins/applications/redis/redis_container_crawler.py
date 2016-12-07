from icrawl_plugin import IContainerCrawler
from plugins.applications.redis import feature
import dockercontainer
from requests.exceptions import ConnectionError
import redis
import logging

logger = logging.getLogger('crawlutils')


class RedisContainerCrawler(IContainerCrawler):
    '''
    Crawling app provided metrics for redis container on docker.
    Usually redis listens on port 6379.
    '''

    feature_type = "application"
    feature_key = "redis"
    default_port = 6379

    def get_feature(self):
        return self.feature_type

    def crawl(self, container_id=None, **kwargs):

        # only crawl redis container. Otherwise, quit.
        c = dockercontainer.DockerContainer(container_id)
        if c.image_name.find(self.feature_key) == -1:
            logger.debug("%s is not %s container" %
                         (c.image_name, self.feature_key))
            raise NameError("this is not target crawl container")

        # extract IP and Port information
        ip = c.get_container_ip()
        ports = c.get_container_ports()

        # set default port number
        if len(ports) == 0:
            ports.append(self.default_port)

        # query to all available ports
        for port in ports:
            client = redis.Redis(host=ip, port=port)
            try:
                metrics = client.info()
            except ConnectionError:
                logger.info("redis does not listen on port:%d", port)
                continue
            feature_attributes = feature.create_feature(metrics)
            return [(self.feature_key, feature_attributes, self.feature_type)]

        # any ports are not available
        raise ConnectionError("no listen ports")
