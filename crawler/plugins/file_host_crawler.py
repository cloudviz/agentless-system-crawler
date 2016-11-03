try:
    from crawler.icrawl_plugin import IHostCrawler
    from crawler.plugins.file_crawler import crawl_files
except ImportError:
    from icrawl_plugin import IHostCrawler
    from plugins.file_crawler import crawl_files


class FileHostCrawler(IHostCrawler):

    def get_feature(self):
        return 'file'

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
        return crawl_files(root_dir=root_dir,
                           exclude_dirs=exclude_dirs)
