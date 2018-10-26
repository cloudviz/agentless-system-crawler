import logging

from icrawl_plugin import IHostCrawler
from utils.package_utils import crawl_packages

logger = logging.getLogger('crawlutils')


class PackageHostCrawler(IHostCrawler):

    def get_feature(self):
        return 'package'

    def crawl(self, root_dir='/', **kwargs):
        return crawl_packages(root_dir=root_dir, reload_needed=False)
