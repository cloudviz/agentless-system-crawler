from icrawl_plugin import IVMCrawler
import logging

try:
    import psvmi
except ImportError:
    psvmi = None

logger = logging.getLogger('crawlutils')


class load_vm_crawler(IVMCrawler):

    def get_feature(self):
        return 'load'

    def crawl(self, vm_desc, **kwargs):
        raise NotImplementedError()
