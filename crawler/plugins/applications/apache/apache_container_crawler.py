from utils.namespace import run_as_another_namespace
import logging
import json
import utils.misc
import dockercontainer
from icrawl_plugin import IContainerCrawler
from plugins.applications.apache import apache_crawler
from requests.exceptions import ConnectionError

logger = logging.getLogger('crawlutils')


class ApacheContainerCrawler(IContainerCrawler):
    feature_type = 'application'
    feature_key = 'apache'
    default_port = 80

    def get_feature(self):
        return self.feature_key

    def crawl(self, container_id=None, **kwargs):

        c = dockercontainer.DockerContainer(container_id)

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
        try:
            metrics = apache_crawler.retrieve_metrics(ip, port)
            return [(self.feature_key, metrics, self.feature_type)]
        except:
            logger.info("apache does not listen on port:%d", port)
            raise ConnectionError("apache does not listen on port:%d", port)
