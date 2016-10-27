try:
    from crawler.plugins.config_crawler import crawl_config_files
    from crawler.icrawl_plugin import IHostCrawler
except ImportError:
    from plugins.config_crawler import crawl_config_files
    from icrawl_plugin import IHostCrawler
import logging

logger = logging.getLogger('crawlutils')


class ConfigHostCrawler(IHostCrawler):

    def get_feature(self):
        return 'config'

    def crawl(self, root_dir='/', exclude_dirs=[], known_config_files=[],
              discover_config_files=False, **kwargs):
        return crawl_config_files(
            root_dir=root_dir,
            exclude_dirs=exclude_dirs,
            known_config_files=known_config_files,
            discover_config_files=discover_config_files)
