from icrawl_plugin import IHostCrawler
from plugins.applications.redis import feature
from requests.exceptions import ConnectionError
import redis
import logging

logger = logging.getLogger('crawlutils')


class RedisHostCrawler(IHostCrawler):
    '''
    Crawling app provided metrics for redis on host.
    Usually redis listens on port 6379.
    '''

    feature_type = "application"
    feature_key = "redis"
    default_port = 6379

    def get_feature(self):
        return self.feature_type

    # TODO: prepare an useful way to set host/port
    def crawl(self, root_dir='/', **kwargs):
        try:
            client = redis.Redis(host='localhost', port=self.default_port)
            metrics = client.info()
        except ConnectionError:
            logger.info("redis does not listen on port:%d", self.default_port)
            raise ConnectionError("no listen at %d", self.default_port)

        feature_attributes = feature.create_feature(metrics)

        return [(self.feature_key, feature_attributes, self.feature_type)]
