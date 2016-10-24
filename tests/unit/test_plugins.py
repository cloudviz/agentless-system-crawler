import mock
import unittest
import types
from collections import namedtuple

# for OUTVM psvmi
from mock import Mock
import sys
sys.modules['psvmi'] = Mock()

# TODO: remove
from crawler.features_crawler import FeaturesCrawler

# TODO: remove
from crawler.crawlmodes import Modes

from crawler.features import (
    OSFeature,
    ConfigFeature,
    DiskFeature,
    PackageFeature,
    MemoryFeature,
    CpuFeature,
    InterfaceFeature,
    LoadFeature,
    DockerPSFeature)
from crawler.container import Container
from crawler.crawler_exceptions import CrawlError
# from crawler.icrawl_plugin import IContainerCrawler
from crawler.plugins.os_container_crawler import OSContainerCrawler
from crawler.plugins.os_host_crawler import OSHostCrawler
from crawler.plugins.os_vm_crawler import os_vm_crawler


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

psvmi_interface = namedtuple(
    'psvmi_interface',
    'ifname bytes_sent bytes_recv packets_sent packets_recv errout errin')

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
psutils_net = namedtuple(
    'psutils_net',
    'bytes_sent bytes_recv packets_sent packets_recv errout errin')


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


class PluginTests(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_init(self, *args):
        FeaturesCrawler()

    @mock.patch('crawler.features_crawler.time.time',
                side_effect=lambda: 123)
    def test_cache(self, mocked_time, *args):
        fc = FeaturesCrawler()
        fc._cache_put_value('k', 'v')
        assert fc._cache_get_value('k') == ('v', 123)
        assert fc._cache_get_value('ble') == (None, None)

    @mock.patch('crawler.plugins.os_crawler.time.time',
                side_effect=lambda: 1001)
    @mock.patch('crawler.plugins.os_crawler.platform.platform',
                side_effect=lambda: 'platform')
    @mock.patch('crawler.plugins.os_crawler.misc.get_host_ip4_addresses',
                side_effect=lambda: ['1.1.1.1'])
    @mock.patch('crawler.plugins.os_crawler.psutil.boot_time',
                side_effect=lambda: 1000)
    @mock.patch('crawler.plugins.os_crawler.platform.system',
                side_effect=lambda: 'linux')
    @mock.patch('crawler.plugins.os_crawler.platform.machine',
                side_effect=lambda: 'machine')
    @mock.patch(
        'crawler.plugins.os_crawler.osinfo.get_osinfo',
        side_effect=lambda mount_point=None: {
            'os': 'os',
            'version': 'os_version'})
    def test_os_host_cawler_plugin(self, *args):
        fc = OSHostCrawler()
        for os in fc.crawl():
            print os
            assert os == (
                'linux',
                OSFeature(
                    boottime=1000,
                    uptime=1,
                    ipaddr=['1.1.1.1'],
                    os='os',
                    os_version='os_version',
                    os_kernel='platform',
                    architecture='machine'),
                'os')

        for i, arg in enumerate(args):
            if i > 0:  # time.time is called more than once
                continue
            assert arg.call_count == 1

    @mock.patch('crawler.plugins.os_crawler.platform.system',
                side_effect=throw_os_error)
    def test_os_host_crawler_plugin_failure(self, *args):
        fc = OSHostCrawler()
        with self.assertRaises(OSError):
            for os in fc.crawl():
                pass

    @mock.patch(
        'crawler.plugins.os_crawler.osinfo.get_osinfo',
        side_effect=lambda mount_point=None: {
            'os': 'os',
            'version': 'os_version'})
    def test_os_host_crawler_plugin_mountpoint_mode(self, *args):
        fc = OSHostCrawler()
        for os in fc.crawl(root_dir='/a'):
            print os
            assert os == (
                'linux',
                OSFeature(
                    boottime='unsupported',
                    uptime='unsupported',
                    ipaddr='0.0.0.0',
                    os='os',
                    os_version='os_version',
                    os_kernel='unknown',
                    architecture='unknown'),
                'os')
        for i, arg in enumerate(args):
            assert arg.call_count == 1

    @mock.patch('crawler.plugins.os_crawler.osinfo.get_osinfo',
                side_effect=throw_os_error)
    def test_os_host_crawler_plugin_mountpoint_mode_failure(self, *args):
        fc = OSHostCrawler()
        with self.assertRaises(OSError):
            for os in fc.crawl(root_dir='/a'):
                pass

    @mock.patch('crawler.plugins.os_crawler.time.time',
                side_effect=lambda: 1001)
    @mock.patch('crawler.plugins.os_crawler.platform.platform',
                side_effect=lambda: 'platform')
    @mock.patch('crawler.plugins.os_crawler.misc.get_host_ip4_addresses',
                side_effect=lambda: ['1.1.1.1'])
    @mock.patch('crawler.plugins.os_crawler.psutil.boot_time',
                side_effect=lambda: 1000)
    @mock.patch('crawler.plugins.os_crawler.platform.system',
                side_effect=lambda: 'linux')
    @mock.patch('crawler.plugins.os_crawler.platform.machine',
                side_effect=lambda: 'machine')
    @mock.patch(
        ("crawler.plugins.os_container_crawler."
            "run_as_another_namespace"),
        side_effect=mocked_run_as_another_namespace)
    @mock.patch(
        ("crawler.plugins.os_container_crawler."
            "dockerutils.exec_dockerinspect"),
        side_effect=lambda long_id: {'State': {'Pid': 123}})
    @mock.patch(
        'crawler.plugins.os_crawler.osinfo.get_osinfo',
        side_effect=lambda mount_point=None: {
            'os': 'os',
            'version': 'os_version'})
    def test_os_container_crawler_plugin(self, *args):
        fc = OSContainerCrawler()
        for os in fc.crawl(container_id=123):
            print os
            assert os == (
                'linux',
                OSFeature(
                    boottime=1000,
                    uptime=1,
                    ipaddr=['1.1.1.1'],
                    os='os',
                    os_version='os_version',
                    os_kernel='platform',
                    architecture='machine'),
                'os')
        for i, arg in enumerate(args):
            if i > 0:  # time.time is called more than once
                continue
            assert arg.call_count == 1

    @mock.patch(
        ("crawler.plugins.os_container_crawler."
            "dockerutils.exec_dockerinspect"),
        side_effect=lambda long_id: {'State': {'Pid': 123}})
    @mock.patch(
        ("crawler.plugins.os_container_crawler.dockerutils."
            "get_docker_container_rootfs_path"),
        side_effect=lambda long_id: '/a/b/c')
    @mock.patch(
        'crawler.plugins.os_crawler.osinfo.get_osinfo',
        side_effect=lambda mount_point=None: {
            'os': 'os',
            'version': 'os_version'})
    def test_os_container_crawler_plugin_avoidsetns(self, *args):
        fc = OSContainerCrawler()
        for os in fc.crawl(container_id=123, avoid_setns=True):
            print os
            assert os == (
                'linux',
                OSFeature(
                    boottime='unsupported',
                    uptime='unsupported',
                    ipaddr='0.0.0.0',
                    os='os',
                    os_version='os_version',
                    os_kernel='unknown',
                    architecture='unknown'),
                'os')
        for i, arg in enumerate(args):
            print i, arg
            if i == 0:
                # get_osinfo()
                assert arg.call_count == 1
                arg.assert_called_with(mount_point='/a/b/c')
            elif i == 1:
                # get_docker_container_rootfs_path
                assert arg.call_count == 1
                arg.assert_called_with(123)
            else:
                # exec_dockerinspect
                assert arg.call_count == 1
                arg.assert_called_with(123)

    @mock.patch(
        ("crawler.plugins.os_container_crawler."
            "dockerutils.exec_dockerinspect"),
        side_effect=lambda long_id: {'State': {'Pid': 123}})
    @mock.patch(
        ("crawler.plugins.os_container_crawler.dockerutils."
            "get_docker_container_rootfs_path"),
        side_effect=throw_os_error)
    def test_os_container_crawler_plugin_avoidsetns_failure(self, *args):
        fc = OSContainerCrawler()
        with self.assertRaises(OSError):
            for os in fc.crawl(container_id=123, avoid_setns=True):
                pass

    @mock.patch('crawler.plugins.os_vm_crawler.psvmi.context_init',
                side_effect=lambda dn1, dn2, kv, d, a: 1000)
    @mock.patch('crawler.plugins.os_vm_crawler.psvmi.system_info',
                side_effect=lambda vmc: psvmi_sysinfo(1000,
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
    def test_os_vm_crawler_plugin_without_vm(self, *args):
        fc = os_vm_crawler()
        for os in fc.crawl(vm_desc=('dn', '2.6', 'ubuntu', 'x86')):
            assert os == (
                'ostype',
                OSFeature(
                    boottime=1000,
                    uptime='unknown',
                    ipaddr='1.1.1.1',
                    os='ostype',
                    os_version='osversion',
                    os_kernel='osrelease',
                    architecture='osplatform'),
                'os')
            pass
        assert args[0].call_count == 1
