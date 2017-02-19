import logging

import dockercontainer
from icrawl_plugin import IContainerCrawler
from plugins.applications.tomcat import tomcat_crawler
from utils.crawler_exceptions import CrawlError

logger = logging.getLogger('crawlutils')


class TomcatContainerCrawler(IContainerCrawler):
    feature_type = 'application'
    feature_key = 'tomcat'
    default_port = 8080

    def get_feature(self):
        return self.feature_key

    def crawl(self, container_id=None, **kwargs):
        password = "password"
        user = "tomcat"

        if "password" in kwargs:
            password = kwargs["password"]

        if "user" in kwargs:
            user = kwargs["user"]

        c = dockercontainer.DockerContainer(container_id)

        # check image name
        if c.image_name.find(self.feature_key) == -1:
            logger.error("%s is not %s container",
                         c.image_name,
                         self.feature_key)
            raise CrawlError("%s does not have expected name for %s (name=%s)",
                             container_id,
                             self.feature_key,
                             c.image_name)

        # extract IP and Port information
        ip = c.get_container_ip()
        ports = c.get_container_ports()

        # crawl all candidate ports
        for each_port in ports:
                return tomcat_crawler.retrieve_metrics(
                    host=ip,
                    port=each_port,
                    user=user,
                    password=password,
                    feature_type=self.feature_type
                )

        raise CrawlError("%s has no accessible endpoint for %s",
                         container_id,
                         self.feature_key)
