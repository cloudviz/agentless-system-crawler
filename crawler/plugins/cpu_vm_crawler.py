try:
    from crawler.icrawl_plugin import IVMCrawler
except ImportError:
    from icrawl_plugin import IVMCrawler
import logging

# External dependencies that must be pip install'ed separately

try:
    import psvmi
except ImportError:
    psvmi = None

logger = logging.getLogger('crawlutils')


class cpu_vm_crawler(IVMCrawler):

    def get_feature(self):
        return 'cpu'

    def crawl(self, vm_desc, **kwargs):
        raise NotImplementedError('Unsupported crawl mode')
