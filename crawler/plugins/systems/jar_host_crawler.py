from icrawl_plugin import IHostCrawler
from utils.jar_utils import crawl_jar_files


class JarHostCrawler(IHostCrawler):

    def get_feature(self):
        return 'jar'

    def crawl(
            self,
            root_dir='/',
            exclude_dirs=[
                '/boot',
                '/dev',
                '/proc',
                '/sys',
                '/mnt',
                '/tmp',
                '/var/cache',
                '/usr/share/man',
                '/usr/share/doc',
                '/usr/share/mime'],
            **kwargs):
        return crawl_jar_files(root_dir=root_dir,
                               exclude_dirs=exclude_dirs)
