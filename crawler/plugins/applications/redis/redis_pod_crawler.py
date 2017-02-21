from icrawl_plugin import IPodCrawler
from plugins.applications.redis import feature
from requests.exceptions import ConnectionError
import redis
import logging

logger = logging.getLogger('crawlutils')


class RedisPodCrawler(IPodCrawler):
    '''
    Crawling app provided metrics for redis container on docker/k8s.
    usually redis listens on port 6379.
    '''

    def __init__(self):
        self.feature_type = "application"
        self.feature_key = "redis"
        self.default_port = 6379

    def get_feature(self):
        return self.feature_key

    def crawl(self, pod, **kwargs):
        '''
        pod equals to V1Pod objects
        see REST definition in the following link
        https://kubernetes.io/docs/api-reference/v1/definitions/#_v1_pod
        '''
        print pod.metadata.labels
        if self.feature_key not in pod.metadata.labels['app']:
            raise NameError("not %s container" % self.feature_key)

        # retrive ip & port info
        ip = pod.status.pod_ip
        port = pod.spec.containers[0].ports[0].container_port

        # access redis endpoint
        client = redis.Redis(host=ip, port=port)
        try:
            metrics = client.info()
        except ConnectionError as ce:
            logger.info("redis does not listen on port:%d", port)
            raise ce

        feature_attributes = feature.create_feature(metrics)
        return [(self.feature_key, feature_attributes, self.feature_type)]
