from icrawl_plugin import IHostCrawler
from utils.os_utils import crawl_os, crawl_os_mountpoint


class OSHostCrawler(IHostCrawler):

    def get_feature(self):
        return 'os'

    def crawl(self, root_dir='/', **kwargs):
        if root_dir == '/':
            return crawl_os()
        else:
            return crawl_os_mountpoint(root_dir)
