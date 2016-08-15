import mock
import unittest
import os
import requests
import copy
import shutil
import types
from collections import namedtuple

from crawler.features_crawler import FeaturesCrawler
from crawler.crawlmodes import Modes
from crawler.features import (
    OSFeature,
    ConfigFeature,
    DiskFeature,
    MetricFeature,
    PackageFeature,
    MemoryFeature,
    CpuFeature,
    InterfaceFeature,
    LoadFeature,
    DockerPSFeature)
from crawler.container import Container
from crawler.crawler_exceptions import CrawlError


class DummyContainer(Container):

    def __init__(self, long_id):
        self.pid = '1234'
        self.long_id = long_id

    def get_memory_cgroup_path(self, node):
        return '/cgroup/%s' % node

    def get_cpu_cgroup_path(self, node):
        return '/cgroup/%s' % node

# for OUTVM psvmi
psvmi_sysinfo = namedtuple('psvmi_sysinfo',
                           '''boottime ipaddr osdistro osname osplatform osrelease
                        ostype osversion memory_used memory_buffered
                        memory_cached memory_free''')

psvmi_memory = namedtuple(
    'psvmi_memory',
    'memory_used memory_buffered memory_cached memory_free')

os_stat = namedtuple(
    'os_stat',
    '''st_mode st_gid st_uid st_atime st_ctime st_mtime st_size''')


def mocked_os_walk(root_dir):
    files = ['file1', 'file2', 'file3']
    dirs = ['dir']
    yield ('/', dirs, files)

    # simulate the os_walk behavior (if a dir is deleted, we don't walk it)
    if '/dir' in dirs:
        files = ['file4']
        dirs = []
        yield ('/dir', dirs, files)


def mocked_os_walk_for_avoidsetns(root_dir):
    files = ['file1', 'file2', 'file3']
    dirs = ['dir']
    yield ('/1/2/3', dirs, files)

    # simulate the os_walk behavior (if a dir is deleted, we don't walk it)
    if '/1/2/3/dir' in dirs:
        files = ['file4']
        dirs = []
        yield ('/dir', dirs, files)

# XXX can't do self.count = for some reason
mcount = 0


class MockedMemCgroupFile(mock.Mock):

    def __init__(self):
        pass

    def readline(self):
        return '2'

    def __iter__(self):
        return self

    def next(self):
        global mcount
        mcount += 1
        if mcount == 1:
            return 'total_cache 100'
        if mcount == 2:
            return 'total_active_file 200'
        else:
            raise StopIteration()

# XXX can't do self.count = for some reason
ccount = 0
ccount2 = 0


class MockedCpuCgroupFile(mock.Mock):

    def __init__(self):
        pass

    def readline(self):
        global ccount2
        ccount2 += 1
        if ccount2 == 1:
            return '1e7'
        else:
            return '2e7'

    def __iter__(self):
        return self

    def next(self):
        global ccount
        ccount += 1
        if ccount == 1:
            return 'system 20'
        if ccount == 2:
            return 'user 20'
        else:
            raise StopIteration()


class MockedFile(mock.Mock):

    def __init__(self):
        pass

    def read(self):
        return 'content'


def mocked_codecs_open(filename, mode, encoding, errors):
    m = mock.Mock()
    m.__enter__ = mock.Mock(return_value=MockedFile())
    m.__exit__ = mock.Mock(return_value=False)
    return m


def mocked_cpu_cgroup_open(filename, mode):
    m = mock.Mock()
    m.__enter__ = mock.Mock(return_value=MockedCpuCgroupFile())
    m.__exit__ = mock.Mock(return_value=False)
    print filename
    return m


def mocked_memory_cgroup_open(filename, mode):
    m = mock.Mock()
    m.__enter__ = mock.Mock(return_value=MockedMemCgroupFile())
    m.__exit__ = mock.Mock(return_value=False)
    print filename
    return m

partition = namedtuple('partition', 'device fstype mountpoint opts')
pdiskusage = namedtuple('pdiskusage', 'percent total')
meminfo = namedtuple('meminfo', 'rss vms')
ioinfo = namedtuple('ioinfo', 'read_bytes write_bytes')
psutils_memory = namedtuple('psutils_memory', 'used free buffers cached')
psutils_cpu = namedtuple(
    'psutils_cpu',
    'idle nice user iowait system irq steal')
psutils_net = namedtuple('psutils_net', 'bytes_sent bytes_recv packets_sent packets_recv errout errin')


def mocked_disk_partitions(all):
    return [partition('/dev/a', 'type', '/a', 'opts'),
            partition('/dev/b', 'type', '/b', 'opts')]


class Connection():

    def __init__(self):
        self.laddr = ['1.1.1.1', '22']
        self.raddr = ['2.2.2.2', '22']
        self.status = 'Established'


class Process():

    def __init__(self, name):
        self.name = name
        self.cmdline = ['cmd']
        self.pid = 123
        self.status = 'Running'
        self.cwd = '/bin'
        self.ppid = 1
        self.create_time = 1000

    def num_threads(self):
        return 1

    def username(self):
        return 'don quijote'

    def get_open_files(self):
        return []

    def get_connections(self):
        return [Connection()]

    def get_memory_info(self):
        return meminfo(10, 20)

    def get_io_counters(self):
        return ioinfo(10, 20)

    def get_cpu_percent(self, interval):
        return 30

    def get_memory_percent(self):
        return 30

STAT_DIR_MODE = 16749


def mocked_os_lstat(path):
    print path
    if path == '/':
        return os_stat(STAT_DIR_MODE, 2, 3, 4, 5, 6, 7)
    elif path == '/file1':
        return os_stat(1, 2, 3, 4, 5, 6, 7)
    elif path == '/file2':
        return os_stat(1, 2, 3, 4, 5, 6, 7)
    elif path == '/file3':
        return os_stat(1, 2, 3, 4, 5, 6, 7)
    elif path == '/dir':
        return os_stat(STAT_DIR_MODE, 2, 3, 4, 5, 6, 7)
    else:
        return os_stat(1, 2, 3, 4, 5, 6, 7)


def mocked_run_as_another_namespace(pid, ns, function, *args, **kwargs):
    result = function(*args)
    # if res is a generator (i.e. function uses yield)
    if isinstance(result, types.GeneratorType):
        result = list(result)
    return result


def throw_os_error(*args, **kvargs):
    raise OSError()


class FeaturesCrawlerTests(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_init(self, *args):
        fc = FeaturesCrawler()

    @mock.patch('crawler.features_crawler.time.time',
                side_effect=lambda: 123)
    def test_cache(self, mocked_time, *args):
        fc = FeaturesCrawler()
        fc._cache_put_value('k', 'v')
        assert fc._cache_get_value('k') == ('v', 123)
        assert fc._cache_get_value('ble') == (None, None)
        assert mocked_time.call_count == 1

    @mock.patch('crawler.features_crawler.platform.platform',
                side_effect=lambda: 'platform')
    @mock.patch('crawler.features_crawler.misc.get_host_ip4_addresses',
                side_effect=lambda: ['1.1.1.1'])
    @mock.patch('crawler.features_crawler.platform.linux_distribution',
                side_effect=lambda: ['linux'])
    @mock.patch('crawler.features_crawler.psutil.boot_time',
                side_effect=lambda: 1000)
    @mock.patch('crawler.features_crawler.time.time',
                side_effect=lambda: 1001)
    @mock.patch('crawler.features_crawler.platform.machine',
                side_effect=lambda: 'machine')
    @mock.patch('crawler.features_crawler.platform.release',
                side_effect=lambda: '123v12345')
    @mock.patch('crawler.features_crawler.platform.version',
                side_effect=lambda: 'v12345')
    @mock.patch('crawler.features_crawler.platform.system',
                side_effect=lambda: 'system')
    def test_crawl_os_invm_mode(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.INVM)
        for os in fc.crawl_os():
            print os
            assert os == (
                'system',
                OSFeature(
                    boottime=1000,
                    uptime=1,
                    ipaddr=['1.1.1.1'],
                    osdistro='linux',
                    osname='platform',
                    osplatform='machine',
                    osrelease='123v12345',
                    ostype='system',
                    osversion='v12345'))
        for i, arg in enumerate(args):
            if i == 0:
                # system() is called twice
                assert arg.call_count == 2
            else:
                assert arg.call_count == 1

    @mock.patch('crawler.features_crawler.platform.platform',
                side_effect=lambda: 'platform')
    @mock.patch('crawler.features_crawler.platform.system',
                side_effect=throw_os_error)
    @mock.patch('crawler.features_crawler.misc.get_host_ip4_addresses',
                side_effect=lambda: ['1.1.1.1'])
    @mock.patch('crawler.features_crawler.platform.linux_distribution',
                side_effect=lambda: ['linux'])
    @mock.patch('crawler.features_crawler.psutil.boot_time',
                side_effect=lambda: 1000)
    @mock.patch('crawler.features_crawler.time.time',
                side_effect=lambda: 1001)
    @mock.patch('crawler.features_crawler.platform.machine',
                side_effect=lambda: 'machine')
    @mock.patch('crawler.features_crawler.platform.release',
                side_effect=lambda: '123v12345')
    @mock.patch('crawler.features_crawler.platform.version',
                side_effect=lambda: 'v12345')
    def test_crawl_os_invm_mode_failure(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.INVM)
        with self.assertRaises(OSError):
            for os in fc.crawl_os():
                pass

    @mock.patch(
        'crawler.features_crawler.platform_outofband.linux_distribution',
        side_effect=lambda prefix: ['linux'])
    @mock.patch('crawler.features_crawler.platform_outofband.platform',
                side_effect=lambda prefix: 'machine')
    @mock.patch('crawler.features_crawler.platform_outofband.machine',
                side_effect=lambda prefix: 'machine')
    @mock.patch('crawler.features_crawler.platform_outofband.release',
                side_effect=lambda prefix: '123v12345')
    @mock.patch('crawler.features_crawler.platform_outofband.version',
                side_effect=lambda prefix: 'v12345')
    @mock.patch('crawler.features_crawler.platform_outofband.system',
                side_effect=lambda prefix: 'system')
    def test_crawl_os_mountpoint_mode(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.MOUNTPOINT)
        for os in fc.crawl_os():
            print os
            assert os == (
                'system',
                OSFeature(
                    boottime='unsupported',
                    uptime='unsupported',
                    ipaddr='0.0.0.0',
                    osdistro='linux',
                    osname='machine',
                    osplatform='machine',
                    osrelease='123v12345',
                    ostype='system',
                    osversion='v12345'))
        for i, arg in enumerate(args):
            if i == 0:
                # system() is called twice
                assert arg.call_count == 2
            else:
                assert arg.call_count == 1

    @mock.patch(
        'crawler.features_crawler.platform_outofband.linux_distribution',
        side_effect=throw_os_error)
    @mock.patch('crawler.features_crawler.platform_outofband.platform',
                side_effect=lambda prefix: 'machine')
    @mock.patch('crawler.features_crawler.platform_outofband.machine',
                side_effect=lambda prefix: 'machine')
    @mock.patch('crawler.features_crawler.platform_outofband.release',
                side_effect=lambda prefix: '123v12345')
    @mock.patch('crawler.features_crawler.platform_outofband.version',
                side_effect=lambda prefix: 'v12345')
    @mock.patch('crawler.features_crawler.platform_outofband.system',
                side_effect=lambda prefix: 'system')
    def test_crawl_os_mountpoint_mode_failure(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.MOUNTPOINT)
        with self.assertRaises(OSError):
            for os in fc.crawl_os():
                pass

    def test_crawl_os_outcontainer_mode_without_container_failure(self, *args):
        with self.assertRaises(ValueError):
            fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER)

    @mock.patch('crawler.features_crawler.platform.platform',
                side_effect=lambda: 'platform')
    @mock.patch('crawler.features_crawler.misc.get_host_ip4_addresses',
                side_effect=lambda: ['1.1.1.1'])
    @mock.patch('crawler.features_crawler.platform.linux_distribution',
                side_effect=lambda: ['linux'])
    @mock.patch('crawler.features_crawler.psutil.boot_time',
                side_effect=lambda: 1000)
    @mock.patch('crawler.features_crawler.time.time',
                side_effect=lambda: 1001)
    @mock.patch('crawler.features_crawler.platform.machine',
                side_effect=lambda: 'machine')
    @mock.patch('crawler.features_crawler.platform.release',
                side_effect=lambda: '123v12345')
    @mock.patch('crawler.features_crawler.platform.version',
                side_effect=lambda: 'v12345')
    @mock.patch('crawler.features_crawler.run_as_another_namespace',
                side_effect=mocked_run_as_another_namespace)
    @mock.patch('crawler.features_crawler.platform.system',
                side_effect=lambda: 'system')
    def test_crawl_os_outcontainer_mode(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer(123))
        for os in fc.crawl_os():
            print os
            assert os == (
                'system',
                OSFeature(
                    boottime=1000,
                    uptime=1,
                    ipaddr=['1.1.1.1'],
                    osdistro='linux',
                    osname='platform',
                    osplatform='machine',
                    osrelease='123v12345',
                    ostype='system',
                    osversion='v12345'))
        for i, arg in enumerate(args):
            if i == 0:
                # system() is called twice
                assert arg.call_count == 2
            else:
                assert arg.call_count == 1

    @mock.patch(
        'crawler.features_crawler.dockerutils.get_docker_container_rootfs_path',
        side_effect=lambda long_id: '/a/b/c')
    @mock.patch(
        'crawler.features_crawler.platform_outofband.linux_distribution',
        side_effect=lambda prefix: ['linux'])
    @mock.patch('crawler.features_crawler.platform_outofband.platform',
                side_effect=lambda prefix: 'machine')
    @mock.patch('crawler.features_crawler.platform_outofband.machine',
                side_effect=lambda prefix: 'machine')
    @mock.patch('crawler.features_crawler.platform_outofband.release',
                side_effect=lambda prefix: '123v12345')
    @mock.patch('crawler.features_crawler.platform_outofband.version',
                side_effect=lambda prefix: 'v12345')
    @mock.patch('crawler.features_crawler.platform_outofband.system',
                side_effect=lambda prefix: 'system')
    def test_crawl_os_outcontainer_mode_avoidsetns(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer('xxxx'))
        for os in fc.crawl_os(avoid_setns=True):
            print os
            assert os == (
                'system',
                OSFeature(
                    boottime='unsupported',
                    uptime='unsupported',
                    ipaddr='0.0.0.0',
                    osdistro='linux',
                    osname='machine',
                    osplatform='machine',
                    osrelease='123v12345',
                    ostype='system',
                    osversion='v12345'))
        for i, arg in enumerate(args):
            print i, arg
            if i == 0:
                # system() is called twice
                assert arg.call_count == 2
                arg.assert_called_with(prefix='/a/b/c')
            elif i == 6:
                # get_docker_container_rootfs_path
                assert arg.call_count == 1
                arg.assert_called_with('xxxx')
            else:
                assert arg.call_count == 1
                arg.assert_called_with(prefix='/a/b/c')

    @mock.patch(
        'crawler.features_crawler.dockerutils.get_docker_container_rootfs_path',
        side_effect=lambda long_id: '/a/b/c')
    @mock.patch(
        'crawler.features_crawler.platform_outofband.linux_distribution',
        side_effect=throw_os_error)
    @mock.patch('crawler.features_crawler.platform_outofband.platform',
                side_effect=lambda prefix: 'machine')
    @mock.patch('crawler.features_crawler.platform_outofband.machine',
                side_effect=lambda prefix: 'machine')
    @mock.patch('crawler.features_crawler.platform_outofband.release',
                side_effect=lambda prefix: '123v12345')
    @mock.patch('crawler.features_crawler.platform_outofband.version',
                side_effect=lambda prefix: 'v12345')
    @mock.patch('crawler.features_crawler.platform_outofband.system',
                side_effect=lambda prefix: 'system')
    def test_crawl_os_container_mode_avoidsetns_failure(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer('xxxx'))
        with self.assertRaises(OSError):
            for os in fc.crawl_os(avoid_setns=True):
                pass

    def test_crawl_os_outvm_mode_without_vm_failure(self, *args):
        with self.assertRaises(ValueError):
            fc = FeaturesCrawler(crawl_mode=Modes.OUTVM)

    @mock.patch('crawler.features_crawler.system_info',
                side_effect=lambda dn, kv, d, a: psvmi_sysinfo(1000,
                                                               '1.1.1.1',
                                                               'osdistro',
                                                               'osname',
                                                               'osplatform',
                                                               'osrelease',
                                                               'ostype',
                                                               'osversion',
                                                               1000000,
                                                               100000,
                                                               100000,
                                                               100000))
    def test_crawl_os_outvm_mode_without_vm(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTVM,
                             vm=('dn', '2.6', 'ubuntu', 'x86'))
        for os in fc.crawl_os():
            pass
        assert args[0].call_count == 1
        args[0].assert_called_with('dn', '2.6', 'ubuntu', 'x86')

    @mock.patch('crawler.features_crawler.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.os.walk',
                side_effect=mocked_os_walk)
    @mock.patch('crawler.features_crawler.os.lstat',
                side_effect=mocked_os_lstat)
    def test_crawl_files_invm_mode(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.INVM)
        for (k, f) in fc.crawl_files():
            print f
            assert f.mode in [1, STAT_DIR_MODE] and f.gid == 2 and f.uid == 3
            assert f.atime == 4 and f.ctime == 5
            assert f.mtime == 6 and f.size == 7
            assert f.name in ['', 'dir', 'file1', 'file2', 'file3', 'file4']
            assert f.path in ['/', '/file1', '/file2', '/file3',
                              '/dir', '/dir/file4']
            assert f.type in ['file', 'dir']
            assert f.linksto is None
        assert args[0].call_count == 6
        assert args[1].call_count == 1  # oswalk
        args[1].assert_called_with('/')
        assert args[2].call_count == 1  # isdir
        args[2].assert_called_with('/')

    @mock.patch('crawler.features_crawler.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.os.walk',
                side_effect=mocked_os_walk)
    @mock.patch('crawler.features_crawler.os.lstat',
                side_effect=mocked_os_lstat)
    def test_crawl_files_invm_mode_with_exclude_dirs(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.INVM)
        for (k, f) in fc.crawl_files(exclude_dirs=['dir']):
            print f
            assert f.mode in [1, STAT_DIR_MODE] and f.gid == 2 and f.uid == 3
            assert f.atime == 4 and f.ctime == 5
            assert f.mtime == 6 and f.size == 7
            assert f.name in ['', 'file1', 'file2', 'file3', 'file4']
            assert f.path in ['/', '/file1', '/file2', '/file3']
            assert f.path not in ['/dir', '/dir/file4']
            assert f.type in ['file', 'dir']
            assert f.linksto is None
        assert args[0].call_count == 4
        assert args[1].call_count == 1  # oswalk
        args[1].assert_called_with('/')
        assert args[2].call_count == 1  # isdir
        args[2].assert_called_with('/')

    @mock.patch('crawler.features_crawler.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.os.walk', side_effect=lambda p: [
                ('/a/b/c', [], ['file1', 'file2', 'file3'])])
    @mock.patch('crawler.features_crawler.os.lstat',
                side_effect=mocked_os_lstat)
    def test_crawl_files_invm_mode_with_alias(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.INVM)
        # This means: crawl at root /a/b/c and replace the /a/b/c with /d
        for (k, f) in fc.crawl_files(root_dir='/a/b/c', root_dir_alias='/d'):
            print f
            assert f.mode in [1, STAT_DIR_MODE] and f.gid == 2 and f.uid == 3
            assert f.atime == 4 and f.ctime == 5
            assert f.mtime == 6 and f.size == 7
            assert f.name in ['d', 'file1', 'file2', 'file3']
            assert f.path in ['/d', '/d/file1', '/d/file2', '/d/file3']
            assert f.type in ['file', 'dir']
            assert f.linksto is None
        assert args[0].call_count == 4
        assert args[1].call_count == 1  # oswalk
        args[1].assert_called_with('/a/b/c')
        assert args[2].call_count == 1  # isdir
        args[2].assert_called_with('/a/b/c')

    @mock.patch('crawler.features_crawler.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.os.walk',
                side_effect=throw_os_error)
    @mock.patch('crawler.features_crawler.os.lstat',
                side_effect=mocked_os_lstat)
    def test_crawl_files_invm_mode_failure(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.INVM)
        with self.assertRaises(OSError):
            for (k, f) in fc.crawl_files(root_dir='/a/b/c'):
                pass

    @mock.patch('crawler.features_crawler.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.os.walk', side_effect=lambda p: [
                ('/a/b/c', ['d'], ['file1', 'file2', 'file3'])])
    @mock.patch('crawler.features_crawler.os.lstat',
                side_effect=mocked_os_lstat)
    def test_crawl_files_mountpoint_mode(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.MOUNTPOINT)
        for (k, f) in fc.crawl_files(root_dir='/a/b/c'):
            assert f.mode in [1, STAT_DIR_MODE] and f.gid == 2 and f.uid == 3
            assert f.atime == 4 and f.ctime == 5
            assert f.mtime == 6 and f.size == 7
            assert f.name in ['c', 'd', 'file1', 'file2', 'file3']
            assert f.path in [
                '/a/b/c',
                '/a/b/c/d',
                '/a/b/c/file1',
                '/a/b/c/file2',
                '/a/b/c/file3']
            assert f.type in ['file', 'dir']
            assert f.linksto is None
        assert args[0].call_count == 5
        assert args[1].call_count == 1  # oswalk
        args[1].assert_called_with('/a/b/c')
        assert args[2].call_count == 1  # isdir
        args[2].assert_called_with('/a/b/c')

    @mock.patch('crawler.features_crawler.run_as_another_namespace',
                side_effect=mocked_run_as_another_namespace)
    @mock.patch('crawler.features_crawler.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.os.walk',
                side_effect=mocked_os_walk)
    @mock.patch('crawler.features_crawler.os.lstat',
                side_effect=mocked_os_lstat)
    def test_crawl_files_outcontainer_mode(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer(123))
        for (k, f) in fc.crawl_files(root_dir='/'):
            assert f.mode in [1, STAT_DIR_MODE] and f.gid == 2 and f.uid == 3
            assert f.atime == 4 and f.ctime == 5
            assert f.mtime == 6 and f.size == 7
            assert f.name in ['', 'dir', 'file1', 'file2', 'file3', 'file4']
            assert f.path in ['/', '/file1', '/file2', '/file3',
                              '/dir', '/dir/file4']
            assert f.type in ['file', 'dir']
            assert f.linksto is None
        assert args[0].call_count == 6
        assert args[1].call_count == 1  # oswalk
        args[1].assert_called_with('/')
        assert args[2].call_count == 1  # isdir
        args[2].assert_called_with('/')

    @mock.patch('crawler.features_crawler.os.walk',
                side_effect=throw_os_error)
    @mock.patch('crawler.features_crawler.run_as_another_namespace',
                side_effect=mocked_run_as_another_namespace)
    @mock.patch('crawler.features_crawler.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.os.lstat',
                side_effect=mocked_os_lstat)
    def test_crawl_files_outcontainer_mode_failure(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer(123))
        with self.assertRaises(OSError):
            for (k, f) in fc.crawl_files(root_dir='/a/b/c'):
                pass

    @mock.patch(
        'crawler.features_crawler.dockerutils.get_docker_container_rootfs_path',
        side_effect=lambda long_id: '/1/2/3')
    @mock.patch('crawler.features_crawler.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.os.walk',
                side_effect=mocked_os_walk_for_avoidsetns)
    @mock.patch('crawler.features_crawler.os.lstat',
                side_effect=mocked_os_lstat)
    def test_crawl_files_outcontainer_mode_avoidsetns(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer(123))
        for (k, f) in fc.crawl_files(root_dir='/', avoid_setns=True):
            print f
            assert f.mode in [1, STAT_DIR_MODE] and f.gid == 2 and f.uid == 3
            assert f.atime == 4 and f.ctime == 5
            assert f.mtime == 6 and f.size == 7
            assert f.name in ['', 'dir', 'file1', 'file2', 'file3', 'file4']
            assert f.path in ['/', '/file1', '/file2', '/file3',
                              '/dir', '/dir/file4']
            assert f.type in ['file', 'dir']
            assert f.linksto is None
        assert args[0].call_count == 6
        assert args[1].call_count == 1  # oswalk
        args[1].assert_called_with('/1/2/3')
        assert args[2].call_count == 1  # isdir
        args[2].assert_called_with('/1/2/3')

    @mock.patch('crawler.features_crawler.run_as_another_namespace',
                side_effect=mocked_run_as_another_namespace)
    @mock.patch('crawler.features_crawler.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.os.walk',
                side_effect=mocked_os_walk)
    @mock.patch('crawler.features_crawler.os.lstat',
                side_effect=mocked_os_lstat)
    def test_crawl_files_outcontainer_mode_with_exclude_dirs(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer(123))
        for (k, f) in fc.crawl_files(root_dir='/',
                                     exclude_dirs=['dir']):
            assert f.mode in [1, STAT_DIR_MODE] and f.gid == 2 and f.uid == 3
            assert f.atime == 4 and f.ctime == 5
            assert f.mtime == 6 and f.size == 7
            assert f.name in ['', 'file1', 'file2', 'file3', 'file4']
            assert f.path in ['/', '/file1', '/file2', '/file3']
            assert f.path not in ['/dir', '/dir/file4']
            assert f.type in ['file', 'dir']
            assert f.linksto is None
        assert args[0].call_count == 4
        assert args[1].call_count == 1  # oswalk
        args[1].assert_called_with('/')
        assert args[2].call_count == 1  # isdir
        args[2].assert_called_with('/')

    @mock.patch(
        'crawler.features_crawler.dockerutils.get_docker_container_rootfs_path',
        side_effect=lambda long_id: '/1/2/3')
    @mock.patch('crawler.features_crawler.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.os.walk',
                side_effect=mocked_os_walk_for_avoidsetns)
    @mock.patch('crawler.features_crawler.os.lstat',
                side_effect=mocked_os_lstat)
    def test_crawl_files_outcontainer_mode_avoidsetns_with_exclude_dirs(
            self,
            *
            args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer(123))
        for (k, f) in fc.crawl_files(root_dir='/',
                                     avoid_setns=True,
                                     exclude_dirs=['/dir']):
            assert f.mode in [1, STAT_DIR_MODE] and f.gid == 2 and f.uid == 3
            assert f.atime == 4 and f.ctime == 5
            assert f.mtime == 6 and f.size == 7
            assert f.name in ['', 'file1', 'file2', 'file3', 'file4']
            assert f.path in ['/', '/file1', '/file2', '/file3']
            assert f.path not in ['/dir', '/dir/file4']
            assert f.type in ['file', 'dir']
            assert f.linksto is None
        assert args[0].call_count == 4
        assert args[1].call_count == 1  # oswalk
        args[1].assert_called_with('/1/2/3')
        assert args[2].call_count == 1  # isdir
        args[2].assert_called_with('/1/2/3')

    @mock.patch('crawler.features_crawler.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.os.path.exists',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.os.lstat',
                side_effect=mocked_os_lstat)
    @mock.patch('crawler.features_crawler.codecs.open',
                side_effect=mocked_codecs_open)
    def test_crawl_config_invm_mode(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.INVM)
        for (k, f) in fc.crawl_config_files(known_config_files=['/etc/file1']):
            assert f == ConfigFeature(name='file1', content='content',
                                      path='/etc/file1')
        assert args[0].call_count == 1  # lstat

    @mock.patch('crawler.features_crawler.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.os.walk', side_effect=lambda p: [
                ('/', [], ['file1', 'file2', 'file3.conf'])])
    @mock.patch('crawler.features_crawler.os.path.exists',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.os.path.isfile',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.os.path.getsize',
                side_effect=lambda p: 1000)
    @mock.patch('crawler.features_crawler.os.lstat',
                side_effect=mocked_os_lstat)
    @mock.patch('crawler.features_crawler.codecs.open',
                side_effect=mocked_codecs_open)
    def test_crawl_config_invm_mode_discover(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.INVM)
        for (k, f) in fc.crawl_config_files(known_config_files=['/etc/file1'],
                                            discover_config_files=True):
            assert ((f == ConfigFeature(name='file1', content='content',
                                        path='/etc/file1')) or
                    (f == ConfigFeature(name='file3.conf', content='content',
                                        path='/file3.conf')))
        assert args[0].call_count == 2  # lstat

    @mock.patch('crawler.features_crawler.run_as_another_namespace',
                side_effect=mocked_run_as_another_namespace)
    @mock.patch('crawler.features_crawler.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.os.path.exists',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.os.lstat',
                side_effect=mocked_os_lstat)
    @mock.patch('crawler.features_crawler.codecs.open',
                side_effect=mocked_codecs_open)
    def test_crawl_config_outcontainer_mode(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer(123))
        for (k, f) in fc.crawl_config_files(known_config_files=['/etc/file1']):
            assert f == ConfigFeature(name='file1', content='content',
                                      path='/etc/file1')
        assert args[0].call_count == 1  # codecs open

    @mock.patch('crawler.features_crawler.run_as_another_namespace',
                side_effect=mocked_run_as_another_namespace)
    @mock.patch('crawler.features_crawler.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.os.walk', side_effect=lambda p: [
                ('/', [], ['file1', 'file2', 'file3.conf'])])
    @mock.patch('crawler.features_crawler.os.path.exists',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.os.path.isfile',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.os.path.getsize',
                side_effect=lambda p: 1000)
    @mock.patch('crawler.features_crawler.os.lstat',
                side_effect=mocked_os_lstat)
    @mock.patch('crawler.features_crawler.codecs.open',
                side_effect=mocked_codecs_open)
    def test_crawl_config_outcontainer_mode_discover(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer(123))
        for (k, f) in fc.crawl_config_files(known_config_files=['/etc/file1'],
                                            discover_config_files=True):
            assert ((f == ConfigFeature(name='file1', content='content',
                                        path='/etc/file1')) or
                    (f == ConfigFeature(name='file3.conf', content='content',
                                        path='/file3.conf')))
        assert args[0].call_count == 2  # codecs open

    @mock.patch(
        'crawler.features_crawler.dockerutils.get_docker_container_rootfs_path',
        side_effect=lambda long_id: '/1/2/3')
    @mock.patch('crawler.features_crawler.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.os.path.exists',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.os.lstat',
                side_effect=mocked_os_lstat)
    @mock.patch('crawler.features_crawler.codecs.open',
                side_effect=mocked_codecs_open)
    def test_crawl_config_outcontainer_mode_avoidsetns(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer(123))
        for (k, f) in fc.crawl_config_files(known_config_files=['/etc/file1'],
                                            avoid_setns=True):
            assert f == ConfigFeature(name='file1', content='content',
                                      path='/etc/file1')
        assert args[0].call_count == 1  # lstat

    @mock.patch(
        'crawler.features_crawler.dockerutils.get_docker_container_rootfs_path',
        side_effect=lambda long_id: '/1/2/3')
    @mock.patch('crawler.features_crawler.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.os.walk', side_effect=lambda p: [
                ('/', [], ['file1', 'file2', 'file3.conf'])])
    @mock.patch('crawler.features_crawler.os.path.exists',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.os.path.isfile',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.os.path.getsize',
                side_effect=lambda p: 1000)
    @mock.patch('crawler.features_crawler.os.lstat',
                side_effect=mocked_os_lstat)
    @mock.patch('crawler.features_crawler.codecs.open',
                side_effect=mocked_codecs_open)
    def test_crawl_config_outcontainer_mode_avoidsetns_discover(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer(123))
        for (k, f) in fc.crawl_config_files(known_config_files=['/etc/file1'],
                                            discover_config_files=True,
                                            avoid_setns=True):
            assert ((f == ConfigFeature(name='file1', content='content',
                                        path='/etc/file1')) or
                    (f == ConfigFeature(name='file3.conf', content='content',
                                        path='/file3.conf')))
        assert args[0].call_count == 2  # lstat

    @mock.patch('crawler.features_crawler.psutil.disk_partitions',
                side_effect=mocked_disk_partitions)
    @mock.patch('crawler.features_crawler.psutil.disk_usage',
                side_effect=lambda x: pdiskusage(10, 100))
    def test_crawl_disk_partitions_invm_mode(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.INVM)
        for (k, f) in fc.crawl_disk_partitions():
            assert (
                f == DiskFeature(
                    partitionname='/dev/a',
                    freepct=90.0,
                    fstype='type',
                    mountpt='/a',
                    mountopts='opts',
                    partitionsize=100) or (
                    f == DiskFeature(
                        partitionname='/dev/b',
                        freepct=90.0,
                        fstype='type',
                        mountpt='/b',
                        mountopts='opts',
                        partitionsize=100)))
        assert args[0].call_count == 2  # disk usage

    @mock.patch('crawler.features_crawler.run_as_another_namespace',
                side_effect=mocked_run_as_another_namespace)
    @mock.patch('crawler.features_crawler.psutil.disk_partitions',
                side_effect=mocked_disk_partitions)
    @mock.patch('crawler.features_crawler.psutil.disk_usage',
                side_effect=lambda x: pdiskusage(10, 100))
    def test_crawl_disk_partitions_outcontainer_mode(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer(123))
        for (k, f) in fc.crawl_disk_partitions():
            assert (
                f == DiskFeature(
                    partitionname='/dev/a',
                    freepct=90.0,
                    fstype='type',
                    mountpt='/a',
                    mountopts='opts',
                    partitionsize=100) or (
                    f == DiskFeature(
                        partitionname='/dev/b',
                        freepct=90.0,
                        fstype='type',
                        mountpt='/b',
                        mountopts='opts',
                        partitionsize=100)))
        assert args[2].call_count == 1  # run as another namespace
        assert args[0].call_count == 2  # disk usage

    @mock.patch('crawler.features_crawler.psutil.process_iter',
                side_effect=lambda: [Process('init')])
    def test_crawl_processes_invm_mode(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.INVM)
        for (k, f) in fc.crawl_processes():
            print f
            assert f.pname == 'init'
            assert f.cmd == 'cmd'
            assert f.pid == 123
        assert args[0].call_count == 1

    @mock.patch('crawler.features_crawler.psutil.process_iter',
                side_effect=lambda: [Process('init')])
    @mock.patch('crawler.features_crawler.run_as_another_namespace',
                side_effect=mocked_run_as_another_namespace)
    def test_crawl_processes_outcontainer_mode(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer(123))
        for (k, f) in fc.crawl_processes():
            print f
            assert f.pname == 'init'
            assert f.cmd == 'cmd'
            assert f.pid == 123
        assert args[0].call_count == 1

    @mock.patch('crawler.features_crawler.psutil.process_iter',
                side_effect=lambda: [Process('init')])
    def test_crawl_connections_invm_mode(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.INVM)
        for (k, f) in fc.crawl_connections():
            assert f.localipaddr == '1.1.1.1'
            assert f.remoteipaddr == '2.2.2.2'
            assert f.localport == '22'
            assert f.remoteport == '22'
        assert args[0].call_count == 1

    @mock.patch('crawler.features_crawler.psutil.process_iter',
                side_effect=lambda: [Process('init')])
    @mock.patch('crawler.features_crawler.run_as_another_namespace',
                side_effect=mocked_run_as_another_namespace)
    def test_crawl_connections_outcontainer_mode(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer(123))
        for (k, f) in fc.crawl_connections():
            assert f.localipaddr == '1.1.1.1'
            assert f.remoteipaddr == '2.2.2.2'
            assert f.localport == '22'
            assert f.remoteport == '22'
        assert args[0].call_count == 1

    @mock.patch('crawler.features_crawler.psutil.process_iter',
                side_effect=lambda: [Process('init')])
    def test_crawl_metrics_invm_mode(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.INVM)
        for (k, f) in fc.crawl_metrics():
            assert f.cpupct == 30.0
            assert f.mempct == 30.0
            assert f.pname == 'init'
            assert f.pid == 123
            assert f.rss == 10
            assert f.status == 'Running'
            assert f.vms == 20
            assert f.read == 10
            assert f.write == 20
        assert args[0].call_count == 1

    @mock.patch('crawler.features_crawler.psutil.process_iter',
                side_effect=lambda: [Process('init')])
    @mock.patch('crawler.features_crawler.round',
                side_effect=throw_os_error)
    def test_crawl_metrics_invm_mode_failure(self, *args):
        with self.assertRaises(CrawlError):
            fc = FeaturesCrawler(crawl_mode=Modes.INVM)
            for ff in fc.crawl_metrics():
                pass
        assert args[0].call_count == 1

    @mock.patch('crawler.features_crawler.psutil.process_iter',
                side_effect=lambda: [Process('init')])
    @mock.patch('crawler.features_crawler.run_as_another_namespace',
                side_effect=mocked_run_as_another_namespace)
    def test_crawl_metrics_outcontainer_mode(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer(123))
        for (k, f) in fc.crawl_metrics():
            assert f.cpupct == 30.0
            assert f.mempct == 30.0
            assert f.pname == 'init'
            assert f.pid == 123
            assert f.rss == 10
            assert f.status == 'Running'
            assert f.vms == 20
            assert f.read == 10
            assert f.write == 20
        assert args[0].call_count == 1

    @mock.patch('crawler.features_crawler.platform.system',
                side_effect=lambda: 'linux')
    @mock.patch('crawler.features_crawler.platform.linux_distribution',
                side_effect=lambda: ['ubuntu'])
    @mock.patch('crawler.features_crawler.os.path.exists',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.get_dpkg_packages',
                side_effect=lambda a, b, c: [('pkg1',
                                              PackageFeature(None, 'pkg1',
                                                             123, 'v1',
                                                             'x86'))])
    def test_crawl_packages_invm_mode_dpkg(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.INVM)
        for (k, f) in fc.crawl_packages():
            assert f == PackageFeature(
                installed=None,
                pkgname='pkg1',
                pkgsize=123,
                pkgversion='v1',
                pkgarchitecture='x86')
        assert args[0].call_count == 1
        args[0].assert_called_with('/', 'var/lib/dpkg', 0)

    @mock.patch('crawler.features_crawler.platform.system',
                side_effect=lambda: 'linux')
    @mock.patch('crawler.features_crawler.platform.linux_distribution',
                side_effect=lambda: ['ubuntu'])
    @mock.patch('crawler.features_crawler.os.path.exists',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.get_dpkg_packages',
                side_effect=throw_os_error)
    def test_crawl_packages_invm_mode_dpkg_failure(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.INVM)
        with self.assertRaises(CrawlError):
            for (k, f) in fc.crawl_packages():
                pass
        assert args[0].call_count == 1
        args[0].assert_called_with('/', 'var/lib/dpkg', 0)

    @mock.patch('crawler.features_crawler.platform.system',
                side_effect=lambda: 'linux')
    @mock.patch('crawler.features_crawler.platform.linux_distribution',
                side_effect=lambda: ['redhat'])
    @mock.patch('crawler.features_crawler.os.path.exists',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.get_rpm_packages',
                side_effect=lambda a, b, c, d: [('pkg1',
                                                 PackageFeature(None, 'pkg1',
                                                                123, 'v1',
                                                                'x86'))])
    def test_crawl_packages_invm_mode_rpm(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.INVM)
        for (k, f) in fc.crawl_packages():
            assert f == PackageFeature(
                installed=None,
                pkgname='pkg1',
                pkgsize=123,
                pkgversion='v1',
                pkgarchitecture='x86')
        assert args[0].call_count == 1
        args[0].assert_called_with('/', 'var/lib/rpm', 0, False)

    @mock.patch('crawler.features_crawler.run_as_another_namespace',
                side_effect=mocked_run_as_another_namespace)
    @mock.patch('crawler.features_crawler.platform.system',
                side_effect=lambda: 'linux')
    @mock.patch('crawler.features_crawler.platform.linux_distribution',
                side_effect=lambda: ['ubuntu'])
    @mock.patch('crawler.features_crawler.os.path.exists',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.get_dpkg_packages',
                side_effect=lambda a, b, c: [('pkg1',
                                              PackageFeature(None, 'pkg1',
                                                             123, 'v1',
                                                             'x86'))])
    def test_crawl_packages_outcontainer_mode_dpkg(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer(123))
        for (k, f) in fc.crawl_packages():
            assert f == PackageFeature(
                installed=None,
                pkgname='pkg1',
                pkgsize=123,
                pkgversion='v1',
                pkgarchitecture='x86')
        assert args[0].call_count == 1
        args[0].assert_called_with('/', 'var/lib/dpkg', 0)

    @mock.patch('crawler.features_crawler.run_as_another_namespace',
                side_effect=mocked_run_as_another_namespace)
    @mock.patch(
        'crawler.features_crawler.dockerutils.get_docker_container_rootfs_path',
        side_effect=lambda long_id: '/a/b/c')
    @mock.patch('crawler.features_crawler.platform.system',
                side_effect=lambda: 'linux')
    @mock.patch('crawler.features_crawler.platform.linux_distribution',
                side_effect=lambda: ['ubuntu'])
    @mock.patch('crawler.features_crawler.os.path.exists',
                side_effect=lambda p: True if 'dpkg' in p else False)
    @mock.patch('crawler.features_crawler.get_dpkg_packages',
                side_effect=throw_os_error)
    def test_crawl_packages_outcontainer_mode_dpkg_failure(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer(123))
        with self.assertRaises(CrawlError):
            for (k, f) in fc.crawl_packages():
                pass
        # get_dpkg_packages is called a second time after the first failure.
        # first time is OUTCONTAINER mode with setns
        # second time is OUTCONTAINER mode with avoid_setns
        assert args[0].call_count == 2
        args[0].assert_called_with('/a/b/c', 'var/lib/dpkg', 0)
        args[1].assert_called_with('/a/b/c/var/lib/dpkg')  # path.exists()

    @mock.patch('crawler.features_crawler.run_as_another_namespace',
                side_effect=mocked_run_as_another_namespace)
    @mock.patch(
        'crawler.features_crawler.dockerutils.get_docker_container_rootfs_path',
        side_effect=lambda long_id: '/a/b/c')
    @mock.patch('crawler.features_crawler.platform.system',
                side_effect=lambda: 'linux')
    @mock.patch('crawler.features_crawler.platform.linux_distribution',
                side_effect=lambda: ['redhat'])
    @mock.patch('crawler.features_crawler.os.path.exists',
                side_effect=lambda p: True if 'rpm' in p else False)
    @mock.patch('crawler.features_crawler.get_rpm_packages',
                side_effect=throw_os_error)
    def test_crawl_packages_outcontainer_mode_rpm_failure(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer(123))
        with self.assertRaises(CrawlError):
            for (k, f) in fc.crawl_packages():
                pass
        # get_dpkg_packages is called a second time after the first failure.
        # first time is OUTCONTAINER mode with setns
        # second time is OUTCONTAINER mode with avoid_setns
        assert args[0].call_count == 2
        args[0].assert_called_with('/a/b/c', 'var/lib/rpm', 0, True)
        args[1].assert_called_with('/a/b/c/var/lib/rpm')  # path.exists()

    @mock.patch(
        'crawler.features_crawler.dockerutils.get_docker_container_rootfs_path',
        side_effect=lambda long_id: '/a/b/c')
    @mock.patch('crawler.features_crawler.platform.system',
                side_effect=lambda: 'linux')
    @mock.patch('crawler.features_crawler.platform.linux_distribution',
                side_effect=lambda: ['ubuntu'])
    @mock.patch('crawler.features_crawler.os.path.exists',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.get_dpkg_packages',
                side_effect=lambda a, b, c: [('pkg1',
                                              PackageFeature(None, 'pkg1',
                                                             123, 'v1',
                                                             'x86'))])
    def test_crawl_packages_outcontainer_mode_avoidsetns(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer(123))
        for (k, f) in fc.crawl_packages(avoid_setns=True):
            assert f == PackageFeature(
                installed=None,
                pkgname='pkg1',
                pkgsize=123,
                pkgversion='v1',
                pkgarchitecture='x86')
        assert args[0].call_count == 1

    @mock.patch('crawler.features_crawler.platform.system',
                side_effect=lambda: 'linux')
    @mock.patch('crawler.features_crawler.platform.linux_distribution',
                side_effect=lambda: ['ubuntu'])
    @mock.patch('crawler.features_crawler.os.path.exists',
                side_effect=lambda p: True)
    @mock.patch('crawler.features_crawler.get_dpkg_packages',
                side_effect=lambda a, b, c: [('pkg1',
                                              PackageFeature(None, 'pkg1',
                                                             123, 'v1',
                                                             'x86'))])
    def test_crawl_packages_mountpoint_mode_dpkg(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.MOUNTPOINT)
        for (k, f) in fc.crawl_packages(root_dir='/a/b/c/'):
            assert f == PackageFeature(
                installed=None,
                pkgname='pkg1',
                pkgsize=123,
                pkgversion='v1',
                pkgarchitecture='x86')
        assert args[0].call_count == 1
        args[0].assert_called_with('/a/b/c/', 'var/lib/dpkg', 0)

    @mock.patch('crawler.features_crawler.psutil.virtual_memory',
                side_effect=lambda: psutils_memory(2, 2, 3, 4))
    def test_crawl_memory_invm_mode(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.INVM)
        for (k, f) in fc.crawl_memory():
            assert f == MemoryFeature(
                memory_used=2,
                memory_buffered=3,
                memory_cached=4,
                memory_free=2,
                memory_util_percentage=50)
        assert args[0].call_count == 1

    @mock.patch('crawler.features_crawler.psutil.virtual_memory',
                side_effect=throw_os_error)
    def test_crawl_memory_invm_mode_failure(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.INVM)
        with self.assertRaises(OSError):
            for (k, f) in fc.crawl_memory():
                pass
        assert args[0].call_count == 1

    @mock.patch('crawler.features_crawler.system_info',
                side_effect=lambda dn, kv, d, a: psvmi_memory(10, 20, 30, 40))
    def test_crawl_memory_outvm_mode(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTVM,
                             vm=('dn', '2.6', 'ubuntu', 'x86'))
        for (k, f) in fc.crawl_memory():
            assert f == MemoryFeature(
                memory_used=10,
                memory_buffered=20,
                memory_cached=30,
                memory_free=40,
                memory_util_percentage=1)
        assert args[0].call_count == 1

    @mock.patch('crawler.features_crawler.psutil.virtual_memory',
                side_effect=lambda: psutils_memory(10, 10, 3, 10))
    @mock.patch('crawler.features_crawler.open',
                side_effect=mocked_memory_cgroup_open)
    def test_crawl_memory_outcontainer_mode(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer(123))
        for (k, f) in fc.crawl_memory():
            assert f == MemoryFeature(
                memory_used=2,
                memory_buffered=200,
                memory_cached=100,
                memory_free=0,
                memory_util_percentage=100)
        assert args[0].call_count == 3  # 3 cgroup files

    @mock.patch('crawler.features_crawler.psutil.virtual_memory',
                side_effect=lambda: psutils_memory(10, 10, 3, 10))
    @mock.patch('crawler.features_crawler.open',
                side_effect=throw_os_error)
    def test_crawl_memory_outcontainer_mode_failure(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer(123))
        with self.assertRaises(CrawlError):
            for (k, f) in fc.crawl_memory():
                pass
        assert args[0].call_count == 1  # 1 cgroup files

    @mock.patch(
        'crawler.features_crawler.psutil.cpu_times_percent',
        side_effect=lambda percpu: [
            psutils_cpu(
                10,
                20,
                30,
                40,
                50,
                60,
                70)])
    def test_crawl_cpu_invm_mode(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.INVM)
        for (k, f) in fc.crawl_cpu():
            assert f == CpuFeature(
                cpu_idle=10,
                cpu_nice=20,
                cpu_user=30,
                cpu_wait=40,
                cpu_system=50,
                cpu_interrupt=60,
                cpu_steal=70,
                cpu_util=90)
        assert args[0].call_count == 1

    @mock.patch('crawler.features_crawler.psutil.cpu_times_percent',
                side_effect=throw_os_error)
    def test_crawl_cpu_invm_mode_failure(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.INVM)
        with self.assertRaises(OSError):
            for (k, f) in fc.crawl_cpu():
                pass
        assert args[0].call_count == 1

    @mock.patch(
        'crawler.features_crawler.psutil.cpu_times_percent',
        side_effect=lambda percpu: [
            psutils_cpu(
                10,
                20,
                30,
                40,
                50,
                60,
                70)])
    @mock.patch('crawler.features_crawler.time.sleep')
    @mock.patch('crawler.features_crawler.open',
                side_effect=mocked_cpu_cgroup_open)
    def test_crawl_cpu_outcontainer_mode(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer(123))
        for (k, f) in fc.crawl_cpu():
            assert f == CpuFeature(
                cpu_idle=90.0,
                cpu_nice=20,
                cpu_user=5.0,
                cpu_wait=40,
                cpu_system=5.0,
                cpu_interrupt=60,
                cpu_steal=70,
                cpu_util=10.0)
        assert args[0].call_count == 3

    @mock.patch(
        'crawler.features_crawler.psutil.cpu_times_percent',
        side_effect=lambda percpu: [
            psutils_cpu(
                10,
                20,
                30,
                40,
                50,
                60,
                70)])
    @mock.patch('crawler.features_crawler.time.sleep')
    @mock.patch('crawler.features_crawler.open',
                side_effect=throw_os_error)
    def test_crawl_cpu_outcontainer_mode_failure(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer(123))
        with self.assertRaises(CrawlError):
            for (k, f) in fc.crawl_cpu():
                pass
        assert args[0].call_count == 1


    @mock.patch(
        'crawler.features_crawler.psutil.net_io_counters',
        side_effect=lambda pernic: {'interface1-unit-tests':
                                    psutils_net(
                                        10,
                                        20,
                                        30,
                                        40,
                                        50,
                                        60)})
    def test_crawl_interface_invm_mode(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.INVM)
        for (k, f) in fc.crawl_interface():
            assert f == InterfaceFeature(if_octets_tx=0, if_octets_rx=0, if_packets_tx=0, if_packets_rx=0, if_errors_tx=0, if_errors_rx=0)

        # Each crawl in crawlutils.py instantiates a FeaturesCrawler object

        fc = FeaturesCrawler(crawl_mode=Modes.INVM)
        for (k, f) in fc.crawl_interface():
            assert f == InterfaceFeature(if_octets_tx=0, if_octets_rx=0, if_packets_tx=0, if_packets_rx=0, if_errors_tx=0, if_errors_rx=0)
        assert args[0].call_count == 2

    @mock.patch('crawler.features_crawler.psutil.net_io_counters',
                side_effect=throw_os_error)
    def test_crawl_interface_invm_mode_failure(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.INVM)
        with self.assertRaises(OSError):
            for (k, f) in fc.crawl_interface():
                pass

        # Each crawl in crawlutils.py instantiates a FeaturesCrawler object

        fc = FeaturesCrawler(crawl_mode=Modes.INVM)
        with self.assertRaises(OSError):
            for (k, f) in fc.crawl_interface():
                pass
        assert args[0].call_count == 2

    @mock.patch('crawler.features_crawler.run_as_another_namespace',
                side_effect=mocked_run_as_another_namespace)
    @mock.patch(
        'crawler.features_crawler.psutil.net_io_counters',
        side_effect=lambda pernic: {'eth0':
                                    psutils_net(
                                        10,
                                        20,
                                        30,
                                        40,
                                        50,
                                        60)})
    def test_crawl_interface_outcontainer_mode(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer(123))
        for (k, f) in fc.crawl_interface():
            assert f == InterfaceFeature(if_octets_tx=0, if_octets_rx=0, if_packets_tx=0, if_packets_rx=0, if_errors_tx=0, if_errors_rx=0)

        # Each crawl in crawlutils.py instantiates a FeaturesCrawler object

        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer(123))
        for (k, f) in fc.crawl_interface():
            assert f == InterfaceFeature(if_octets_tx=0, if_octets_rx=0, if_packets_tx=0, if_packets_rx=0, if_errors_tx=0, if_errors_rx=0)
        assert args[0].call_count == 2
        assert args[1].call_count == 2

    @mock.patch('crawler.features_crawler.os.getloadavg',
                side_effect=lambda : [1,2,3])
    def test_crawl_load_invm_mode(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.INVM)
        for (k, f) in fc.crawl_load():
            assert f == LoadFeature(shortterm=1, midterm=2, longterm=2)
        assert args[0].call_count == 1

    @mock.patch('crawler.features_crawler.os.getloadavg',
                side_effect=throw_os_error)
    def test_crawl_load_invm_mode_failure(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.INVM)
        with self.assertRaises(OSError):
            for (k, f) in fc.crawl_load():
                pass
        assert args[0].call_count == 1

    @mock.patch('crawler.features_crawler.run_as_another_namespace',
                side_effect=mocked_run_as_another_namespace)
    @mock.patch('crawler.features_crawler.os.getloadavg',
                side_effect=lambda : [1,2,3])
    def test_crawl_load_outcontainer_mode(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer(123))
        for (k, f) in fc.crawl_load():
            assert f == LoadFeature(shortterm=1, midterm=2, longterm=2)
        assert args[0].call_count == 1
        assert args[1].call_count == 1


    @mock.patch('crawler.features_crawler.dockerutils.exec_dockerps',
                side_effect=lambda : [{'State':{'Running':True},
                                       'Image':'reg/image:latest',
                                       'Config':{'Cmd':'command'},
                                       'Name':'name',
                                       'Id':'id'}])
    def test_crawl_dockerps_invm_mode(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.INVM)
        for (k, f) in fc.crawl_dockerps():
            assert f == DockerPSFeature(Status=True, Created=0, Image='reg/image:latest', Ports=[], Command='command', Names='name', Id='id')
        assert args[0].call_count == 1

    @mock.patch('crawler.features_crawler.dockerutils.exec_dockerps',
                side_effect=throw_os_error)
    def test_crawl_dockerps_invm_mode_failure(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.INVM)
        with self.assertRaises(CrawlError):
            for (k, f) in fc.crawl_dockerps():
                pass
        assert args[0].call_count == 1

    @mock.patch('crawler.features_crawler.dockerutils.exec_docker_history',
                side_effect=lambda long_id : [{'Id':'image1', 'random':'abc'},
                                              {'Id':'image2', 'random':'abc'}])
    def test_crawl_dockerhistory_outcontainer_mode(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer(123))
        for (k, f) in fc.crawl_dockerhistory():
            assert f == {'history': [{'Id': 'image1', 'random': 'abc'},
                                     {'Id': 'image2', 'random': 'abc'}]}
        assert args[0].call_count == 1

    @mock.patch('crawler.features_crawler.dockerutils.exec_docker_history',
                side_effect=throw_os_error)
    def test_crawl_dockerhistory_outcontainer_mode_failure(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer(123))
        with self.assertRaises(CrawlError):
            for (k, f) in fc.crawl_dockerhistory():
                pass
        assert args[0].call_count == 1


    @mock.patch('crawler.features_crawler.dockerutils.exec_dockerinspect',
                side_effect=lambda long_id : {'Id':'image1', 'random':'abc'})
    def test_crawl_dockerinspect_outcontainer_mode(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer(123))
        for (k, f) in fc.crawl_dockerinspect():
            assert f == {'Id': 'image1', 'random': 'abc'}
        assert args[0].call_count == 1

    @mock.patch('crawler.features_crawler.dockerutils.exec_dockerinspect',
                side_effect=throw_os_error)
    def test_crawl_dockerinspect_outcontainer_mode_failure(self, *args):
        fc = FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                             container=DummyContainer(123))
        with self.assertRaises(CrawlError):
            for (k, f) in fc.crawl_dockerinspect():
                pass
        assert args[0].call_count == 1
