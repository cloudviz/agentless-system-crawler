from icrawl_plugin import IHostCrawler
from utils.file_utils import crawl_files


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
                '/var/log',
                '/var/tmp',
                '/var/opt',
                '/var/lib/docker',
                '/var/lib/dpkg',
                '/var/lib/lxcfs',
                '/usr',
                '/etc',
                '/crawler',
                '/bin',
                '/sbin',
                '/lib',
                '/lib64',
                '/lost+found',
                '/root',
                '/srv',
                '/src',
                '/home',
                '/var/cache',
                '/usr/share/man',
                '/usr/share/doc',
                '/usr/share/mime'],
            **kwargs):
        return crawl_files(root_dir=root_dir,
                           exclude_dirs=exclude_dirs)
