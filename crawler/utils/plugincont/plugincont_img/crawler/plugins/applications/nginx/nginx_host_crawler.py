from icrawl_plugin import IHostCrawler
from plugins.applications.nginx import nginx_crawler
import logging

logger = logging.getLogger('crawlutils')


class NginxHostCrawler(IHostCrawler):
    feature_type = 'application'
    feature_key = 'nginx'
    default_port = 80

    def get_feature(self):
        return self.feature_key

    def crawl(self):
        metrics = nginx_crawler.retrieve_metrics(
            host='localhost',
            port=self.default_port
        )
        return [(self.feature_key, metrics, self.feature_type)]
