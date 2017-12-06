import os
import socket
import unittest

import mock

import utils.misc


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
        assert utils.misc.find_mount_point(str(tmpdir)) == '/'

    def test_subprocess_run(self):
        assert utils.misc.subprocess_run(
            'echo abc', shell=True).strip() == 'abc'
        assert utils.misc.subprocess_run('exit 0', shell=True).strip() == ''
        with self.assertRaises(RuntimeError):
            utils.misc.subprocess_run('exit 1', shell=True)
        with self.assertRaises(RuntimeError):
            # There should not be a /a/b/c/d/e file
            utils.misc.subprocess_run('/a/b/c/d/e', shell=False)

    @mock.patch('utils.misc.open')
    def test_get_process_env(self, mock_open):
        mock_open.return_value = open('tests/unit/mock_environ_file')
        env = utils.misc.get_process_env(pid=os.getpid())
        assert 'HOME' in env
        with self.assertRaises(TypeError):
            utils.misc.get_process_env('asdf')

    def test_process_is_crawler(self):
        assert utils.misc.process_is_crawler(os.getpid())
        assert utils.misc.process_is_crawler(1) is False
        # make sure 1123... does not actually exist
        assert utils.misc.process_is_crawler(1123234325123235) is False
        with self.assertRaises(TypeError):
            utils.misc.process_is_crawler('asdf')

    def test_get_host_ip4_addresses(self):
        assert '127.0.0.1' in utils.misc.get_host_ip4_addresses()

    def test_is_process_running(self):
        assert utils.misc.is_process_running(os.getpid())
        assert utils.misc.is_process_running(1)
        # make sure 1123... does not actually exist
        assert utils.misc.is_process_running(1123234325) is False
        with self.assertRaises(TypeError):
            utils.misc.is_process_running('asdf')

    @mock.patch('utils.misc.socket.socket', side_effect=MockedSocket1)
    def test_get_host_ipaddr1(self, mock_socket):
        assert utils.misc.get_host_ipaddr() == '1.2.3.4'

    @mock.patch('utils.misc.socket.socket', side_effect=MockedSocket2)
    @mock.patch('utils.misc.socket.gethostname',
                side_effect=lambda: '4.3.2.1')
    def test_get_host_ipaddr2(self, *args):
        assert utils.misc.get_host_ipaddr() == '4.3.2.1'

    def test_execution_path(self):
        assert utils.misc.execution_path('abc').endswith('/abc')

    # XXX this is more of a functional test
    def test_btrfs_list_subvolumes(self):
        # we either have it installed and it will raise a RuntimeError because
        # the path provided does not exist or it is not and it will raise a
        # RuntimeError.
        with self.assertRaises(RuntimeError):
            for submodule in utils.misc.btrfs_list_subvolumes('asd'):
                pass

    @mock.patch('utils.misc.subprocess_run')
    def test_btrfs_list_subvolumes_with_list(self, mock_run):
        mock_run.return_value = (
            ("ID 257 gen 7 top level 5 path btrfs/subvolumes/a60a763cbaaedd3ac"
             "2b77bff939019fda876d8a187cb7e85789bb36377accbce\n"
             "ID 258 gen 8 top level 5 path btrfs/subvolumes/9212798f648314583"
             "9c72f06a6bc2b0e456ca2b9ec14ea70e2948f098ce51077\n"
             "ID 278 gen 1908 top level 5 path btrfs/subvolumes/7cd6c219c63e02"
             "82ddbd8437c9b2a0220aff40bbfd6734503bcd58e5afa28426\n"))

        assert list(
            utils.misc.btrfs_list_subvolumes('asd')) == [
            [
                'ID',
                '257',
                'gen',
                '7',
                'top',
                'level',
                '5',
                'path',
                ("btrfs/subvolumes/a60a763cbaaedd3ac2b77bff939019fda876d8a187c"
                    "b7e85789bb36377accbce")],
            [
                'ID',
                '258',
                'gen',
                '8',
                'top',
                'level',
                '5',
                'path',
                ("btrfs/subvolumes/9212798f6483145839c72f06a6bc2b0e456ca2b9ec1"
                    "4ea70e2948f098ce51077")],
            [
                'ID',
                '278',
                'gen',
                '1908',
                'top',
                'level',
                '5',
                'path',
                ("btrfs/subvolumes/7cd6c219c63e0282ddbd8437c9b2a0220aff40bbfd6"
                    "734503bcd58e5afa28426")]]
