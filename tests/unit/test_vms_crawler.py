import mock
import unittest
from vms_crawler import VirtualMachinesCrawler


class MockedOSCrawler:

    def crawl(self, vm_desc, **kwargs):
        return [('linux', {'os': 'some_os'}, 'os')]


class MockedCPUCrawler:

    def crawl(self, vm_desc, **kwargs):
        return [('cpu-0', {'used': 100}, 'cpu')]


class MockedOSCrawlerFailure:

    def crawl(self, vm_desc, **kwargs):
        print vm_desc
        if vm_desc[0] == 'errorpid':
            raise OSError('some exception')
        else:
            return [('linux', {'os': 'some_os'}, 'os')]


class MockedQemuVirtualMachine:

    def __init__(self, name='name', pid=777):
        self.namespace = name
        self.name = name
        self.kernel = '2.6'
        self.distro = 'ubuntu'
        self.arch = 'x86'
        self.pid = pid

    def get_metadata_dict(self):
        return {'namespace': self.namespace}

    def get_vm_desc(self):
        return str(self.pid), self.kernel, self.distro, self.arch


class VirtualMachinesCrawlerTests(unittest.TestCase):

    @mock.patch(
        'vms_crawler.plugins_manager.get_vm_crawl_plugins',
        side_effect=lambda features: [(MockedOSCrawler(), {}),
                                      (MockedCPUCrawler(), {})])
    @mock.patch('vms_crawler.get_virtual_machines',
                side_effect=lambda user_list, host_namespace: [
                    MockedQemuVirtualMachine(
                        name='aaa',
                        pid=101),
                    MockedQemuVirtualMachine(
                        name='bbb',
                        pid=102),
                    MockedQemuVirtualMachine(
                        name='ccc',
                        pid=103)])
    def test_vms_crawler(self, *args):
        crawler = VirtualMachinesCrawler(features=['os'], user_list=['abcd'])
        frames = list(crawler.crawl())
        namespaces = sorted([f.metadata['namespace'] for f in frames])
        assert namespaces == sorted(['aaa', 'bbb', 'ccc'])
        features_count = sorted([f.num_features for f in frames])
        assert features_count == sorted([2, 2, 2])
        system_types = sorted([f.metadata['system_type'] for f in frames])
        assert system_types == sorted(['vm', 'vm', 'vm'])
        assert args[0].call_count == 1
        assert args[1].call_count == 1

    @mock.patch(
        'vms_crawler.plugins_manager.get_vm_crawl_plugins',
        side_effect=lambda features: [(MockedOSCrawlerFailure(), {}),
                                      (MockedCPUCrawler(), {})])
    @mock.patch('vms_crawler.get_virtual_machines',
                side_effect=lambda user_list, host_namespace: [
                    MockedQemuVirtualMachine(
                        name='aaa',
                        pid=101),
                    MockedQemuVirtualMachine(
                        name='errorid',
                        pid='errorpid'),
                    MockedQemuVirtualMachine(
                        name='ccc',
                        pid=103)])
    def test_failed_vms_crawler(self, *args):
        crawler = VirtualMachinesCrawler(features=['os'])
        with self.assertRaises(OSError):
            frames = list(crawler.crawl(ignore_plugin_exception=False))
        assert args[0].call_count == 1
        assert args[1].call_count == 1

    @mock.patch(
        'vms_crawler.plugins_manager.get_vm_crawl_plugins',
        side_effect=lambda features: [(MockedCPUCrawler(), {}),
                                      (MockedOSCrawlerFailure(), {}),
                                      (MockedCPUCrawler(), {})])
    @mock.patch('vms_crawler.get_virtual_machines',
                side_effect=lambda user_list, host_namespace: [
                    MockedQemuVirtualMachine(
                        name='aaa',
                        pid=101),
                    MockedQemuVirtualMachine(
                        name='errorid',
                        pid='errorpid'),
                    MockedQemuVirtualMachine(
                        name='ccc',
                        pid=103)])
    def test_failed_vms_crawler_with_ignore_failure(self, *args):
        crawler = VirtualMachinesCrawler(features=['cpu', 'os', 'cpu'])
        frames = list(crawler.crawl())  # defaults to ignore_plugin_exception
        namespaces = sorted([f.metadata['namespace'] for f in frames])
        assert namespaces == sorted(['aaa', 'errorid', 'ccc'])
        features_count = sorted([f.num_features for f in frames])
        assert features_count == sorted([3, 2, 3])
        system_types = [f.metadata['system_type'] for f in frames]
        assert system_types == ['vm', 'vm', 'vm']
        assert args[0].call_count == 1
        assert args[1].call_count == 1


if __name__ == '__main__':
    unittest.main()
