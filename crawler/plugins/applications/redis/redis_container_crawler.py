from icrawl_plugin import IContainerCrawler
from plugins.applications.redis import feature
import dockercontainer
from requests.exceptions import ConnectionError
import logging
from utils.namespace import run_as_another_namespace
import json
import utils.misc


logger = logging.getLogger('crawlutils')


class RedisContainerCrawler(IContainerCrawler):

    '''
    Crawling app provided metrics for redis container on docker.
    Usually redis listens on port 6379.
    '''

    feature_type = "application"
    feature_key = "redis"
    default_port = 6379

    def get_port(self, c):
        port = None

        if "annotation.io.kubernetes.container.ports" in\
                c.inspect['Config']['Labels']:

            ports = c.inspect['Config']['Labels'][
                'annotation.io.kubernetes.container.ports']

            ports = json.loads(ports)

        else:
            ports = c.get_container_ports()

        for each_port in ports:
            tmp_port = None
            if "containerPort" in each_port:
                tmp_port = int(each_port['containerPort'])
            else:
                tmp_port = int(each_port)

            if tmp_port == self.default_port:
                port = tmp_port

        return port

    def get_feature(self):
        return self.feature_key

    def crawl(self, container_id=None, **kwargs):

        try:
            import redis
        except ImportError:
            import pip
            pip.main(['install', 'redis'])
            import redis

        # only crawl redis container. Otherwise, quit.
        c = dockercontainer.DockerContainer(container_id)
        port = self.get_port(c)

        if not port:
            return

        state = c.inspect['State']
        pid = str(state['Pid'])
        ips = run_as_another_namespace(
            pid, ['net'], utils.misc.get_host_ip4_addresses)

        for each_ip in ips:
            if each_ip != "127.0.0.1":
                ip = each_ip
                break

        client = redis.Redis(host=ip, port=port)

        try:
            metrics = client.info()
            feature_attributes = feature.create_feature(metrics)
            return [(self.feature_key, feature_attributes, self.feature_type)]
        except:
            logger.info("redis does not listen on port:%d", port)
            raise ConnectionError("no listen at %d", port)
