from icrawl_plugin import IHostCrawler
from plugins.applications.liberty import liberty_crawler
import logging

logger = logging.getLogger('crawlutils')


class LibertyHostCrawler(IHostCrawler):
    feature_type = 'application'
    feature_key = 'liberty'
    default_port = 9443

    def get_feature(self):
        return self.feature_key

    def crawl(self, **options):
        password = "password"
        user = "user"

        if "password" in options:
            password = options["password"]

        if "user" in options:
            user = options["user"]

        return liberty_crawler.retrieve_metrics(
            host='localhost',
            port=self.default_port,
            user=user,
            password=password,
            feature_type=self.feature_type
        )
