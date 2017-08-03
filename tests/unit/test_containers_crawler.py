import mock
import unittest
from containers_crawler import ContainersCrawler


class MockedOSCrawler:

    def crawl(self, **kwargs):
        return [('linux', {'os': 'some_os'}, 'os')]


class MockedCPUCrawler:

    def crawl(self, **kwargs):
        return [('cpu-0', {'used': 100}, 'cpu')]


class MockedOSCrawlerFailure:

    def crawl(self, container_id, **kwargs):
        if container_id == 'errorid':
            raise OSError('some exception')
        else:
            return [('linux', {'os': 'some_os'}, 'os')]


class MockedDockerContainer:

    def __init__(self, short_id='short_id', pid=777):
        self.namespace = short_id
        self.pid = pid
        self.short_id = short_id
        self.long_id = short_id
        self.name = 'name'
        self.image = 'image'
        self.owner_namespace = 'owner_namespace'
        self.docker_image_long_name = 'image_long_name'
        self.docker_image_short_name = 'image_short_name'
        self.docker_image_tag = 'image_tag'
        self.docker_image_registry = 'image_registry'

    def is_docker_container(self):
        return True

    def link_logfiles(self, options):
        pass

    def unlink_logfiles(self, options):
        pass

    def get_metadata_dict(self):
        return {'namespace': self.namespace}

    def __eq__(self, other):
        return self.pid == other.pid


class ContainersCrawlerTests(unittest.TestCase):

    @mock.patch(
        'containers_crawler.plugins_manager.get_container_crawl_plugins',
        side_effect=lambda features: [(MockedOSCrawler(), {}),
                                      (MockedCPUCrawler(), {})])
    @mock.patch('containers_crawler.get_containers',
                side_effect=lambda host_namespace, user_list: [
                    MockedDockerContainer(
                        short_id='aaa',
                        pid=101),
                    MockedDockerContainer(
                        short_id='bbb',
                        pid=102),
                    MockedDockerContainer(
                        short_id='ccc',
                        pid=103)])
    def test_containers_crawler(self, *args):
        crawler = ContainersCrawler(features=['os'])
        frames = list(crawler.crawl())
        namespaces = sorted([f.metadata['namespace'] for f in frames])
        assert namespaces == sorted(['aaa', 'bbb', 'ccc'])
        features_count = sorted([f.num_features for f in frames])
        assert features_count == sorted([2, 2, 2])
        system_types = sorted([f.metadata['system_type'] for f in frames])
        assert system_types == sorted(['container', 'container', 'container'])
        assert args[0].call_count == 1
        assert args[1].call_count == 1

    @mock.patch(
        'containers_crawler.plugins_manager.get_container_crawl_plugins',
        side_effect=lambda features: [(MockedOSCrawlerFailure(), {}),
                                      (MockedCPUCrawler(), {})])
    @mock.patch('containers_crawler.get_containers',
                side_effect=lambda host_namespace, user_list: [
                    MockedDockerContainer(
                        short_id='aaa',
                        pid=101),
                    MockedDockerContainer(
                        short_id='errorid',
                        pid=102),
                    MockedDockerContainer(
                        short_id='ccc',
                        pid=103)])
    def test_failed_containers_crawler(self, *args):
        crawler = ContainersCrawler(features=['os'])
        with self.assertRaises(OSError):
            frames = list(crawler.crawl(ignore_plugin_exception=False))  # noqa
        assert args[0].call_count == 1
        assert args[1].call_count == 1

    @mock.patch(
        'containers_crawler.plugins_manager.get_container_crawl_plugins',
        side_effect=lambda features: [(MockedCPUCrawler(), {}),
                                      (MockedOSCrawlerFailure(), {}),
                                      (MockedCPUCrawler(), {})])
    @mock.patch('containers_crawler.get_containers',
                side_effect=lambda host_namespace, user_list: [
                    MockedDockerContainer(
                        short_id='aaa',
                        pid=101),
                    MockedDockerContainer(
                        short_id='errorid',
                        pid=102),
                    MockedDockerContainer(
                        short_id='ccc',
                        pid=103)])
    def test_failed_containers_crawler_with_ignore_failure(self, *args):
        crawler = ContainersCrawler(features=['os'])
        frames = list(crawler.crawl())  # defaults to ignore_plugin_exception
        namespaces = sorted([f.metadata['namespace'] for f in frames])
        assert namespaces == sorted(['aaa', 'errorid', 'ccc'])
        features_count = sorted([f.num_features for f in frames])
        assert features_count == sorted([3, 2, 3])
        system_types = [f.metadata['system_type'] for f in frames]
        assert system_types == ['container', 'container', 'container']
        assert args[0].call_count == 1
        assert args[1].call_count == 1


if __name__ == '__main__':
    unittest.main()
