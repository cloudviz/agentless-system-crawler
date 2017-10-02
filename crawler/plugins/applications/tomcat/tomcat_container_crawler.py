import logging
import dockercontainer
from icrawl_plugin import IContainerCrawler
from plugins.applications.tomcat import tomcat_crawler
from utils.namespace import run_as_another_namespace
import json
import utils.misc
from requests.exceptions import ConnectionError

logger = logging.getLogger('crawlutils')


class TomcatContainerCrawler(IContainerCrawler):
    feature_type = 'application'
    feature_key = 'tomcat'
    default_port = 8080

    def get_feature(self):
        return self.feature_key

    def get_opt(self, kwargs):
        password = "password"
        user = "tomcat"

        if "password" in kwargs:
            password = kwargs["password"]

        if "user" in kwargs:
            user = kwargs["user"]

        return password, user

    def crawl(self, container_id=None, **kwargs):

        password, user = self.get_opt(kwargs)
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
            return tomcat_crawler.retrieve_metrics(
                host=ip,
                port=port,
                user=user,
                password=password,
                feature_type=self.feature_type)
        except:
            raise ConnectionError("%s has no accessible endpoint for %s",
                                  container_id,
                                  self.feature_key)
