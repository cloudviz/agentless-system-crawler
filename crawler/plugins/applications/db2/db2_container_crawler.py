import logging
import dockercontainer
from icrawl_plugin import IContainerCrawler
from plugins.applications.db2 import db2_crawler
from utils.namespace import run_as_another_namespace
import json
import utils.misc
from requests.exceptions import ConnectionError

logger = logging.getLogger('crawlutils')


class DB2ContainerCrawler(IContainerCrawler):
    feature_type = 'application'
    feature_key = 'db2'
    default_port = 50000

    def get_feature(self):
        return self.feature_key

    def get_opt(self, kwargs):
        password = "db2inst1"
        user = "db2inst1-pwd"
        db = "sample"

        if "password" in kwargs:
            password = kwargs["password"]

        if "user" in kwargs:
            user = kwargs["user"]

        if "db" in kwargs:
            db = kwargs["db"]

        return password, user, db

    def crawl(self, container_id=None, **kwargs):

        password, user, db = self.get_opt(kwargs)
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
            metrics = db2_crawler.retrieve_metrics(
                host=ip,
                user=user,
                password=password,
                db=db,
            )
            return [(self.feature_key, metrics, self.feature_type)]
        except:
            logger.info("db2 does not listen on port:%d", port)
            raise ConnectionError("db2 does not listen on port:%d", port)
