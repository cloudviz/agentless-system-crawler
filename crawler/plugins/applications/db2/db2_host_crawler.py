from icrawl_plugin import IHostCrawler
from plugins.applications.db2 import db2_crawler
from utils.crawler_exceptions import CrawlError
import logging

logger = logging.getLogger('crawlutils')


class DB2HostCrawler(IHostCrawler):
    feature_type = 'application'
    feature_key = 'db2'

    def get_feature(self):
        return self.feature_key

    def crawl(self, **options):
        password = "db2inst1-pwd"
        user = "db2inst1"
        db = "sample"

        if "password" in options:
            password = options["password"]

        if "user" in options:
            user = options["user"]

        if "db" in options:
            db = options["db"]

        try:
            metrics = db2_crawler.retrieve_metrics(
                host="localhost",
                user=user,
                password=password,
                db=db
            )
            return [(self.feature_key, metrics, self.feature_type)]
        except:
            raise CrawlError("cannot retrice metrics db %s", db)
