import logging
import dockercontainer
from icrawl_plugin import IContainerCrawler
from plugins.applications.nginx import nginx_crawler
from utils.namespace import run_as_another_namespace
from requests.exceptions import ConnectionError
import json
import utils.misc

logger = logging.getLogger('crawlutils')


class NginxContainerCrawler(IContainerCrawler):
    feature_type = 'application'
    feature_key = 'nginx'
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

        # crawl all candidate ports
        try:
            metrics = nginx_crawler.retrieve_metrics(ip, port)
            return [(self.feature_key, metrics, self.feature_type)]
        except:
            logger.error("can't find metrics endpoint at http://%s:%s",
                         ip,
                         port)
            raise ConnectionError("can't find metrics endpoint"
                                  "at http://%s:%s", ip, port)
