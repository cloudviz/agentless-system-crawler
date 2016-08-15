import unittest
import os
import mock
import socket

import crawler.misc


class MockedSocket1():
    def __init__(self, a, b):
        print a, b
        pass
    def connect(self, dest):
        pass
    def getsockname(self):
        return ['1.2.3.4']

class MockedSocket2():
    def __init__(self, a, b):
        print a, b
        pass
    def connect(self, dest):
        pass
    def getsockname(self):
        raise socket.error()
    def gethostname(self):
        return '1.2.3.4'


class MiscTests(unittest.TestCase):
    def test_find_mount_point(self, tmpdir='/'):
        assert crawler.misc.find_mount_point(str(tmpdir)) == '/'

    def test_subprocess_run(self):
        assert crawler.misc.subprocess_run('echo abc', shell=True).strip() == 'abc'
        assert crawler.misc.subprocess_run('exit 0', shell=True).strip() == ''
        with self.assertRaises(RuntimeError):
            crawler.misc.subprocess_run('exit 1', shell=True)
        with self.assertRaises(RuntimeError):
            # There should not be a /a/b/c/d/e file
            crawler.misc.subprocess_run('/a/b/c/d/e', shell=False)

    def test_get_process_env(self):
        env = crawler.misc.get_process_env(pid=os.getpid())
        assert env.has_key('HOME')
        with self.assertRaises(TypeError):
            crawler.misc.get_process_env('asdf')

    def test_process_is_crawler(self):
        assert crawler.misc.process_is_crawler(os.getpid()) == True
        assert crawler.misc.process_is_crawler(1) == False
        # make sure 1123... does not actually exist
        assert crawler.misc.process_is_crawler(1123234325123235) == False
        with self.assertRaises(TypeError):
            crawler.misc.process_is_crawler('asdf')

    def test_get_host_ip4_addresses(self):
        assert '127.0.0.1' in crawler.misc.get_host_ip4_addresses()

    def test_is_process_running(self):
        assert crawler.misc.is_process_running(os.getpid()) == True
        assert crawler.misc.is_process_running(1) == True
        # make sure 1123... does not actually exist
        assert crawler.misc.is_process_running(1123234325) == False
        with self.assertRaises(TypeError):
            crawler.misc.is_process_running('asdf')

    @mock.patch('crawler.misc.socket.socket', side_effect=MockedSocket1)
    def test_get_host_ipaddr1(self, mock_socket):
        assert crawler.misc.get_host_ipaddr() == '1.2.3.4'

    @mock.patch('crawler.misc.socket.socket', side_effect=MockedSocket2)
    @mock.patch('crawler.misc.socket.gethostname',
                side_effect=lambda : '4.3.2.1')
    def test_get_host_ipaddr2(self, *args):
        assert crawler.misc.get_host_ipaddr() == '4.3.2.1'

    def test_execution_path(self):
        assert crawler.misc.execution_path('abc').endswith('/abc')

    # XXX this is more of a functional test
    def test_btrfs_list_subvolumes(self):
        # we either have it installed and it will raise a RuntimeError because
        # the path provided does not exist or it is not and it will raise a
        # RuntimeError.
        with self.assertRaises(RuntimeError):
            for submodule in crawler.misc.btrfs_list_subvolumes('asd'):
                pass

    @mock.patch('crawler.misc.subprocess_run')
    def test_btrfs_list_subvolumes_with_list(self, mock_run):
        mock_run.return_value = ('ID 257 gen 7 top level 5 path btrfs/subvolumes/a60a763cbaaedd3ac2b77bff939019fda876d8a187cb7e85789bb36377accbce\n'
                                 'ID 258 gen 8 top level 5 path btrfs/subvolumes/9212798f6483145839c72f06a6bc2b0e456ca2b9ec14ea70e2948f098ce51077\n'
                                 'ID 278 gen 1908 top level 5 path btrfs/subvolumes/7cd6c219c63e0282ddbd8437c9b2a0220aff40bbfd6734503bcd58e5afa28426\n')

        assert list(crawler.misc.btrfs_list_subvolumes('asd')) == [['ID', '257', 'gen', '7', 'top', 'level', '5', 'path', 'btrfs/subvolumes/a60a763cbaaedd3ac2b77bff939019fda876d8a187cb7e85789bb36377accbce'], ['ID', '258', 'gen', '8', 'top', 'level', '5', 'path', 'btrfs/subvolumes/9212798f6483145839c72f06a6bc2b0e456ca2b9ec14ea70e2948f098ce51077'], ['ID', '278', 'gen', '1908', 'top', 'level', '5', 'path', 'btrfs/subvolumes/7cd6c219c63e0282ddbd8437c9b2a0220aff40bbfd6734503bcd58e5afa28426']]

