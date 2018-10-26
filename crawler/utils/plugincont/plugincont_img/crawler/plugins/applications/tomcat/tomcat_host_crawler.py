from icrawl_plugin import IHostCrawler
from plugins.applications.tomcat import tomcat_crawler
import logging

logger = logging.getLogger('crawlutils')


class TomcatHostCrawler(IHostCrawler):
    feature_type = 'application'
    feature_key = 'tomcat'
    default_port = 8080

    def get_feature(self):
        return self.feature_key

    def crawl(self, **options):
        password = "password"
        user = "tomcat"

        if "password" in options:
            password = options["password"]

        if "user" in options:
            user = options["user"]

        return tomcat_crawler.retrieve_metrics(
            host='localhost',
            port=self.default_port,
            user=user,
            password=password,
            feature_type=self.feature_type
        )
