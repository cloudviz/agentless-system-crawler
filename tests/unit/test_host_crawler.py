import mock
import unittest
from crawler.host_crawler import HostCrawler


class MockedOSCrawler:

    def crawl(self, **kwargs):
        return [('linux', {'os': 'some_os'}, 'os')]


class MockedCPUCrawler:

    def crawl(self, **kwargs):
        return [('cpu-0', {'used': 100}, 'cpu')]


class MockedOSCrawlerFailure:

    def crawl(self, **kwargs):
        raise OSError('some exception')


class HostCrawlerTests(unittest.TestCase):

    @mock.patch(
        'crawler.host_crawler.plugins_manager.get_host_crawl_plugins',
        side_effect=lambda features: [(MockedOSCrawler(), {}),
                                      (MockedCPUCrawler(), {})])
    def test_host_crawler(self, *args):
        crawler = HostCrawler(features=['os', 'cpu'], namespace='localhost')
        frames = list(crawler.crawl())
        namespaces = [f.metadata['namespace'] for f in frames]
        assert namespaces == ['localhost']
        features_count = [f.num_features for f in frames]
        assert features_count == [2]
        system_types = [f.metadata['system_type'] for f in frames]
        assert system_types == ['host']
        assert args[0].call_count == 1

    @mock.patch(
        'crawler.host_crawler.plugins_manager.get_host_crawl_plugins',
        side_effect=lambda features: [(MockedOSCrawlerFailure(), {}),
                                      (MockedCPUCrawler(), {})])
    def test_failed_host_crawler(self, *args):
        crawler = HostCrawler(features=['os', 'cpu'], namespace='localhost')
        with self.assertRaises(OSError):
            frames = list(crawler.crawl(ignore_plugin_exception=False))
        assert args[0].call_count == 1

    @mock.patch(
        'crawler.host_crawler.plugins_manager.get_host_crawl_plugins',
        side_effect=lambda features: [(MockedCPUCrawler(), {}),
                                      (MockedOSCrawlerFailure(), {}),
                                      (MockedCPUCrawler(), {})])
    def test_failed_host_crawler_with_ignore_failure(self, *args):
        crawler = HostCrawler(
            features=[
                'cpu',
                'os',
                'cpu'],
            namespace='localhost')
        frames = list(crawler.crawl())
        namespaces = sorted([f.metadata['namespace'] for f in frames])
        assert namespaces == sorted(['localhost'])
        features_count = [f.num_features for f in frames]
        assert features_count == [2]
        system_types = [f.metadata['system_type'] for f in frames]
        assert system_types == ['host']
        assert args[0].call_count == 1

if __name__ == '__main__':
    unittest.main()
