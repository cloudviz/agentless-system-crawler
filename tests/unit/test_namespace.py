import mock
import unittest
from collections import namedtuple
import Queue
import time

import crawler.namespace

import crawler.crawler_exceptions

os_stat = namedtuple(
    'os_stat',
    '''st_mode st_gid st_uid st_atime st_ctime st_mtime st_size st_ino''')


def throw_os_error(*args, **kvargs):
    raise OSError()


def fun_add(x=0):
    return x + 1


def fun_not_exiting(x=0):
    yield 1
    while True:
        time.sleep(1)


def fun_failed(x=0):
    assert False


class MockedLibc:

    def __init__(self):
        pass

    def setns(self, namespaces, mode):
        pass

    def open(self, path, mode):
        return 1

    def close(self, fd):
        pass

    def prctl(self, *args):
        print args


class MockedLibcNoSetns:

    def __init__(self):
        pass

    def syscall(self, syscall_num, namespaces, mode):
        return 1

    def open(self, path, mode):
        return 1

    def close(self, fd):
        pass

    def prctl(self, *args):
        print args


class MockedLibcFailedOpen:

    def __init__(self):
        pass

    def setns(self, namespaces, mode):
        pass

    def open(self, path, mode):
        return -1

    def close(self, fd):
        pass

    def prctl(self, *args):
        print args


class MockedLibcFailedSetns:

    def __init__(self):
        pass

    def setns(self, namespaces, mode):
        return -1

    def open(self, path, mode):
        return 1

    def close(self, fd):
        pass

    def prctl(self, *args):
        print args


class MockedLibcFailedClose:

    def __init__(self):
        pass

    def setns(self, namespaces, mode):
        pass

    def open(self, path, mode):
        return 1

    def close(self, fd):
        return -1

    def prctl(self, *args):
        print args


class MockedQueue:

    def __init__(self, *args):
        pass

    def get(self, timeout=None):
        return (123, None)

    def put(self, item):
        pass

    def close(self):
        pass


class MockedQueueGetTimeout:

    def __init__(self, *args):
        pass

    def get(self, timeout=None):
        if timeout:
            raise Queue.Empty()

    def put(self, item):
        pass

    def close(self):
        pass


class NamespaceTests(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    @mock.patch('crawler.namespace.os.stat',
                side_effect=lambda p: os_stat(1, 2, 3, 4, 5, 6, 7, 8))
    def test_pid_namespace(self, *args):
        assert crawler.namespace.get_pid_namespace(1) == 8

    @mock.patch('crawler.namespace.os.stat',
                side_effect=throw_os_error)
    def test_pid_namespace_no_process(self, *args):
        assert crawler.namespace.get_pid_namespace(1) is None

    @mock.patch('crawler.namespace.get_libc',
                side_effect=lambda: MockedLibc())
    def test_run_as_another_namespace(self, *args):
        assert crawler.namespace.run_as_another_namespace(
            '1', crawler.namespace.ALL_NAMESPACES, fun_add, 1) == 2

    @mock.patch('crawler.namespace.get_libc',
                side_effect=lambda: MockedLibcFailedOpen())
    def test_run_as_another_namespace_failed_mnt_open(self, *args):
        with self.assertRaises(
                crawler.crawler_exceptions.NamespaceFailedMntSetns):
            crawler.namespace.run_as_another_namespace(
                '1', crawler.namespace.ALL_NAMESPACES, fun_add, 1)

    @mock.patch('crawler.namespace.get_libc',
                side_effect=lambda: MockedLibcFailedOpen())
    def test_run_as_another_namespace_failed_non_mnt_open(self, *args):
        assert crawler.namespace.run_as_another_namespace(
            '1', ['pid', 'net'], fun_add, 1) == 2

    @mock.patch('crawler.namespace.get_libc',
                side_effect=lambda: MockedLibcFailedSetns())
    def test_run_as_another_namespace_failed_setns(self, *args):
        with self.assertRaises(SystemExit):
            crawler.namespace.run_as_another_namespace(
                '1', crawler.namespace.ALL_NAMESPACES, fun_add, 1)

    @mock.patch('crawler.namespace.get_libc',
                side_effect=lambda: MockedLibcFailedSetns())
    def test_run_as_another_namespace_failed_non_mnt_setns(self, *args):
        assert crawler.namespace.run_as_another_namespace(
            '1', ['pid', 'net'], fun_add, 1) == 2

    @mock.patch('crawler.namespace.get_libc',
                side_effect=lambda: MockedLibcFailedClose())
    def test_run_as_another_namespace_failed_close(self, *args):
        assert crawler.namespace.run_as_another_namespace(
            '1', crawler.namespace.ALL_NAMESPACES, fun_add, 1) == 2

    @mock.patch('crawler.namespace.get_libc',
                side_effect=lambda: MockedLibcNoSetns())
    def test_run_as_another_namespace_no_setns(self, *args):
        assert crawler.namespace.run_as_another_namespace(
            '1', crawler.namespace.ALL_NAMESPACES, fun_add, 1) == 2

    @mock.patch('crawler.namespace.get_libc',
                side_effect=lambda: MockedLibc())
    def test_run_as_another_namespace_failed_fun(self, *args):
        with self.assertRaises(AssertionError):
            crawler.namespace.run_as_another_namespace(
                '1', crawler.namespace.ALL_NAMESPACES, fun_failed, 1)

    @mock.patch('crawler.namespace.get_libc',
                side_effect=lambda: MockedLibc())
    @mock.patch('crawler.namespace.multiprocessing.Queue',
                side_effect=MockedQueue)
    def test_run_as_another_namespace_with_mocked_queue(self, *args):
        assert crawler.namespace.run_as_another_namespace(
            '1', crawler.namespace.ALL_NAMESPACES, fun_failed, 1) == 123

    @mock.patch('crawler.namespace.get_libc',
                side_effect=lambda: MockedLibc())
    @mock.patch('crawler.namespace.multiprocessing.Queue',
                side_effect=MockedQueueGetTimeout)
    def test_run_as_another_namespace_get_timeout(self, *args):
        with self.assertRaises(crawler.crawler_exceptions.CrawlTimeoutError):
            crawler.namespace.run_as_another_namespace(
                '1', crawler.namespace.ALL_NAMESPACES, fun_add, 1)

    @mock.patch('crawler.namespace.get_libc',
                side_effect=lambda: MockedLibc())
    @mock.patch('crawler.namespace.multiprocessing.Queue',
                side_effect=MockedQueue)
    def test_run_as_another_namespace_fun_not_exiting_failure(self, *args):
        _old_timeout = crawler.namespace.IN_CONTAINER_TIMEOUT
        crawler.namespace.IN_CONTAINER_TIMEOUT = 0
        with self.assertRaises(crawler.crawler_exceptions.CrawlTimeoutError):
            crawler.namespace.run_as_another_namespace(
                '1', crawler.namespace.ALL_NAMESPACES, fun_not_exiting, 1)
        crawler.namespace.IN_CONTAINER_TIMEOUT = _old_timeout
