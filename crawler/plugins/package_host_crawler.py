try:
    from crawler.package_crawler import crawl_packages
    from crawler.icrawl_plugin import IHostCrawler
except ImportError:
    from package_crawler import crawl_packages
    from icrawl_plugin import IHostCrawler

import logging

logger = logging.getLogger('crawlutils')


class PackageHostCrawler(IHostCrawler):

    def get_feature(self):
        return 'package'

    def crawl(self, root_dir='/', **kwargs):
        return crawl_packages(root_dir=root_dir)
