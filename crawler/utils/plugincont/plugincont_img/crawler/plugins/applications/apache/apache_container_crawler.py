import logging


import dockercontainer
from icrawl_plugin import IContainerCrawler
from plugins.applications.apache import apache_crawler
from utils.crawler_exceptions import CrawlError

logger = logging.getLogger('crawlutils')


class ApacheContainerCrawler(IContainerCrawler):
    feature_type = 'application'
    feature_key = 'apache'

    def get_feature(self):
        return self.feature_key

    def crawl(self, container_id=None, **kwargs):

        c = dockercontainer.DockerContainer(container_id)

        # check image name
        if c.image_name.find("httpd") == -1:

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
        for port in ports:
            try:
                metrics = apache_crawler.retrieve_metrics(ip, port)
            except CrawlError:
                logger.error("can't find metrics endpoint at http://%s:%s",
                             ip,
                             port)
                continue
            return [(self.feature_key, metrics, self.feature_type)]

        raise CrawlError("%s has no accessible endpoint for %s",
                         container_id,
                         self.feature_key)
