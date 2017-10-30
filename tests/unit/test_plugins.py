import types
import unittest
from collections import namedtuple

import os
import sys
import tempfile
from zipfile import ZipFile, ZipInfo

from utils import jar_utils
sys.path.append('tests/unit/')

import mock
from plugins.systems.config_container_crawler import ConfigContainerCrawler
from plugins.systems.config_host_crawler import ConfigHostCrawler
from plugins.systems.connection_container_crawler import ConnectionContainerCrawler
from plugins.systems.connection_host_crawler import ConnectionHostCrawler
from plugins.systems.connection_vm_crawler import ConnectionVmCrawler
from plugins.systems.cpu_container_crawler import CpuContainerCrawler
from plugins.systems.cpu_host_crawler import CpuHostCrawler
from plugins.systems.disk_container_crawler import DiskContainerCrawler
from plugins.systems.disk_host_crawler import DiskHostCrawler
from plugins.systems.dockerhistory_container_crawler import DockerhistoryContainerCrawler
from plugins.systems.dockerinspect_container_crawler import DockerinspectContainerCrawler
from plugins.systems.dockerps_host_crawler import DockerpsHostCrawler
from plugins.systems.file_container_crawler import FileContainerCrawler
from plugins.systems.file_host_crawler import FileHostCrawler
from plugins.systems.interface_container_crawler import InterfaceContainerCrawler
from plugins.systems.interface_host_crawler import InterfaceHostCrawler
from plugins.systems.interface_vm_crawler import InterfaceVmCrawler
from plugins.systems.jar_container_crawler import JarContainerCrawler
from plugins.systems.jar_host_crawler import JarHostCrawler
from plugins.systems.load_container_crawler import LoadContainerCrawler
from plugins.systems.load_host_crawler import LoadHostCrawler
from plugins.systems.memory_container_crawler import MemoryContainerCrawler
from plugins.systems.memory_host_crawler import MemoryHostCrawler
from plugins.systems.memory_vm_crawler import MemoryVmCrawler
from plugins.systems.metric_container_crawler import MetricContainerCrawler
from plugins.systems.metric_host_crawler import MetricHostCrawler
from plugins.systems.metric_vm_crawler import MetricVmCrawler
from plugins.systems.os_container_crawler import OSContainerCrawler
from plugins.systems.os_host_crawler import OSHostCrawler
from plugins.systems.os_vm_crawler import os_vm_crawler
from plugins.systems.package_container_crawler import PackageContainerCrawler
from plugins.systems.package_host_crawler import PackageHostCrawler
from plugins.systems.process_container_crawler import ProcessContainerCrawler
from plugins.systems.process_host_crawler import ProcessHostCrawler
from plugins.systems.process_vm_crawler import process_vm_crawler

from container import Container
from utils.crawler_exceptions import CrawlError
from utils.features import (
    OSFeature,
    ConfigFeature,
    DiskFeature,
    PackageFeature,
    MemoryFeature,
    CpuFeature,
    InterfaceFeature,
    LoadFeature,
    DockerPSFeature,
    JarFeature)


# for OUTVM psvmi


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
        pass

    @mock.patch('utils.os_utils.time.time',
                side_effect=lambda: 1001)
    @mock.patch('utils.os_utils.platform.platform',
                side_effect=lambda: 'platform')
    @mock.patch('utils.os_utils.utils.misc.get_host_ip4_addresses',
                side_effect=lambda: ['1.1.1.1'])
    @mock.patch('utils.os_utils.psutil.boot_time',
                side_effect=lambda: 1000)
    @mock.patch('utils.os_utils.platform.system',
                side_effect=lambda: 'linux')
    @mock.patch('utils.os_utils.platform.machine',
                side_effect=lambda: 'machine')
    @mock.patch(
        'utils.os_utils.osinfo.get_osinfo',
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

    @mock.patch('utils.os_utils.platform.system',
                side_effect=throw_os_error)
    def test_os_host_crawler_plugin_failure(self, *args):
        fc = OSHostCrawler()
        with self.assertRaises(OSError):
            for os in fc.crawl():
                pass

    @mock.patch(
        'utils.os_utils.osinfo.get_osinfo',
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

    @mock.patch('utils.os_utils.osinfo.get_osinfo',
                side_effect=throw_os_error)
    def test_os_host_crawler_plugin_mountpoint_mode_failure(self, *args):
        fc = OSHostCrawler()
        with self.assertRaises(OSError):
            for os in fc.crawl(root_dir='/a'):
                pass

    @mock.patch('utils.os_utils.time.time',
                side_effect=lambda: 1001)
    @mock.patch('utils.os_utils.platform.platform',
                side_effect=lambda: 'platform')
    @mock.patch('utils.os_utils.utils.misc.get_host_ip4_addresses',
                side_effect=lambda: ['1.1.1.1'])
    @mock.patch('utils.os_utils.psutil.boot_time',
                side_effect=lambda: 1000)
    @mock.patch('utils.os_utils.platform.system',
                side_effect=lambda: 'linux')
    @mock.patch('utils.os_utils.platform.machine',
                side_effect=lambda: 'machine')
    @mock.patch(
        ("plugins.systems.os_container_crawler."
            "run_as_another_namespace"),
        side_effect=mocked_run_as_another_namespace)
    @mock.patch(
        ("plugins.systems.os_container_crawler."
            "utils.dockerutils.exec_dockerinspect"),
        side_effect=lambda long_id: {'State': {'Pid': 123}})
    @mock.patch(
        'utils.os_utils.osinfo.get_osinfo',
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
        ("plugins.systems.os_container_crawler."
            "utils.dockerutils.exec_dockerinspect"),
        side_effect=lambda long_id: {'State': {'Pid': 123}})
    @mock.patch(
        ("plugins.systems.os_container_crawler.utils.dockerutils."
            "get_docker_container_rootfs_path"),
        side_effect=lambda long_id: '/a/b/c')
    @mock.patch(
        'utils.os_utils.osinfo.get_osinfo',
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
        ("plugins.systems.os_container_crawler."
            "utils.dockerutils.exec_dockerinspect"),
        side_effect=lambda long_id: {'State': {'Pid': 123}})
    @mock.patch(
        ("plugins.systems.os_container_crawler.utils.dockerutils."
            "get_docker_container_rootfs_path"),
        side_effect=throw_os_error)
    def test_os_container_crawler_plugin_avoidsetns_failure(self, *args):
        fc = OSContainerCrawler()
        with self.assertRaises(OSError):
            for os in fc.crawl(container_id=123, avoid_setns=True):
                pass

    @mock.patch('plugins.systems.os_vm_crawler.psvmi.context_init',
                side_effect=lambda dn1, dn2, kv, d, a: 1000)
    @mock.patch('plugins.systems.os_vm_crawler.psvmi.system_info',
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
    @mock.patch('plugins.systems.os_vm_crawler.psvmi')
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
        assert args[1].call_count == 1

    @mock.patch('utils.file_utils.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('utils.file_utils.os.walk',
                side_effect=mocked_os_walk)
    @mock.patch('utils.file_utils.os.lstat',
                side_effect=mocked_os_lstat)
    def test_file_host_crawler(self, *args):
        fc = FileHostCrawler()
        for (k, f, fname) in fc.crawl():
            print f
            assert fname == "file"
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
        assert args[2].call_count == 2  # isdir
        args[2].assert_called_with('/')

    @mock.patch('utils.file_utils.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('utils.file_utils.os.walk',
                side_effect=mocked_os_walk)
    @mock.patch('utils.file_utils.os.lstat',
                side_effect=mocked_os_lstat)
    def test_file_host_crawler_with_exclude_dirs(self, *args):
        fc = FileHostCrawler()
        for (k, f, fname) in fc.crawl(exclude_dirs=['dir']):
            print f
            assert fname == "file"
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
        assert args[2].call_count == 2  # isdir
        args[2].assert_called_with('/')

    @mock.patch('utils.file_utils.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('utils.file_utils.os.walk',
                side_effect=throw_os_error)
    @mock.patch('utils.file_utils.os.lstat',
                side_effect=mocked_os_lstat)
    def test_file_host_crawler_failure(self, *args):
        fc = FileHostCrawler()
        with self.assertRaises(OSError):
            for (k, f, fname) in fc.crawl(root_dir='/a/b/c'):
                pass

    @mock.patch(
        ("plugins.systems.file_container_crawler."
            "utils.dockerutils.exec_dockerinspect"),
        side_effect=lambda long_id: {'State': {'Pid': 123}})
    @mock.patch(
        ("plugins.systems.file_container_crawler."
            "run_as_another_namespace"),
        side_effect=mocked_run_as_another_namespace)
    @mock.patch('utils.file_utils.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('utils.file_utils.os.walk',
                side_effect=mocked_os_walk)
    @mock.patch('utils.file_utils.os.lstat',
                side_effect=mocked_os_lstat)
    def test_file_container_crawler(self, *args):
        fc = FileContainerCrawler()
        for (k, f, fname) in fc.crawl(root_dir='/'):
            assert fname == "file"
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
        assert args[2].call_count == 2  # isdir
        args[2].assert_called_with('/')

    def test_jar_container_crawler_plugin(self, *args):
        tmpdir = tempfile.mkdtemp()
        jar_file_name = 'myfile.jar'

        # Ensure the file is read/write by the creator only
        saved_umask = os.umask(0077)

        path = os.path.join(tmpdir, jar_file_name)
        try:
            with ZipFile(path, "w") as myjar:
                myjar.writestr(ZipInfo('first.class',(1980,1,1,1,1,1)), "first secrets!")
                myjar.writestr(ZipInfo('second.class',(1980,1,1,1,1,1)), "second secrets!")
                myjar.writestr(ZipInfo('second.txt',(1980,1,1,1,1,1)), "second secrets!")

            fc = JarHostCrawler()
            jars = list(fc.crawl(root_dir=tmpdir))
            #jars = list(jar_utils.crawl_jar_files(root_dir=tmpdir))
            print jars
            jar_feature = jars[0][1]
            assert 'myfile.jar' == jar_feature.name
            assert '48ac85a26ffa7ff5cefdd5c73a9fb888' == jar_feature.jarhash
            assert ['ddc6eff37020aa858e26b1ba8a49ee0e',
                    'cbe2a13eb99c1c8ac5f30d0a04f8c492'] == jar_feature.hashes
            assert 'jar' == jars[0][2]

        except IOError as e:
            print 'IOError'
        finally:
            os.remove(path)

    @mock.patch(
        ("plugins.systems.file_container_crawler."
            "utils.dockerutils.exec_dockerinspect"),
        side_effect=lambda long_id: {'State': {'Pid': 123}})
    @mock.patch('utils.file_utils.os.walk',
                side_effect=throw_os_error)
    @mock.patch(
        ("plugins.systems.file_container_crawler."
            "run_as_another_namespace"),
        side_effect=mocked_run_as_another_namespace)
    @mock.patch('utils.file_utils.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('utils.file_utils.os.lstat',
                side_effect=mocked_os_lstat)
    def test_file_container_crawler_failure(self, *args):
        fc = FileContainerCrawler()
        with self.assertRaises(OSError):
            for (k, f, fname) in fc.crawl(root_dir='/a/b/c'):
                pass

    @mock.patch(
        ("plugins.systems.file_container_crawler."
            "utils.dockerutils.exec_dockerinspect"),
        side_effect=lambda long_id: {'State': {'Pid': 123}})
    @mock.patch(
        ("plugins.systems.file_container_crawler.utils.dockerutils."
            "get_docker_container_rootfs_path"),
        side_effect=lambda long_id: '/1/2/3')
    @mock.patch('utils.file_utils.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('utils.file_utils.os.walk',
                side_effect=mocked_os_walk_for_avoidsetns)
    @mock.patch('utils.file_utils.os.lstat',
                side_effect=mocked_os_lstat)
    def test_file_container_crawler_avoidsetns(self, *args):
        fc = FileContainerCrawler()
        for (k, f, fname) in fc.crawl(root_dir='/', avoid_setns=True):
            print f
            assert fname == "file"
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
        assert args[2].call_count == 2  # isdir
        args[2].assert_called_with('/1/2/3')

    @mock.patch(
        ("plugins.systems.file_container_crawler."
            "utils.dockerutils.exec_dockerinspect"),
        side_effect=lambda long_id: {'State': {'Pid': 123}})
    @mock.patch(
        ("plugins.systems.file_container_crawler."
            "run_as_another_namespace"),
        side_effect=mocked_run_as_another_namespace)
    @mock.patch('utils.file_utils.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('utils.file_utils.os.walk',
                side_effect=mocked_os_walk)
    @mock.patch('utils.file_utils.os.lstat',
                side_effect=mocked_os_lstat)
    def test_file_container_crawler_with_exclude_dirs(self, *args):
        fc = FileContainerCrawler()
        for (k, f, fname) in fc.crawl(root_dir='/',
                                      exclude_dirs=['dir']):
            assert fname == "file"
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
        assert args[2].call_count == 2  # isdir
        args[2].assert_called_with('/')

    @mock.patch(
        ("plugins.systems.file_container_crawler."
            "utils.dockerutils.exec_dockerinspect"),
        side_effect=lambda long_id: {'State': {'Pid': 123}})
    @mock.patch(
        ("plugins.systems.file_container_crawler.utils.dockerutils."
            "get_docker_container_rootfs_path"),
        side_effect=lambda long_id: '/1/2/3')
    @mock.patch('utils.file_utils.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('utils.file_utils.os.walk',
                side_effect=mocked_os_walk_for_avoidsetns)
    @mock.patch('utils.file_utils.os.lstat',
                side_effect=mocked_os_lstat)
    def test_file_container_crawler_avoidsetns_with_exclude_dirs(
            self,
            *
            args):
        fc = FileContainerCrawler()
        for (k, f, fname) in fc.crawl(root_dir='/',
                                      avoid_setns=True,
                                      exclude_dirs=['/dir']):
            assert fname == "file"
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
        assert args[2].call_count == 2  # isdir
        args[2].assert_called_with('/1/2/3')

    @mock.patch('utils.config_utils.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('utils.config_utils.os.path.exists',
                side_effect=lambda p: True)
    @mock.patch('utils.config_utils.os.lstat',
                side_effect=mocked_os_lstat)
    @mock.patch('utils.config_utils.codecs.open',
                side_effect=mocked_codecs_open)
    def test_config_host_crawler(self, *args):
        fc = ConfigHostCrawler()
        for (k, f, fname) in fc.crawl(known_config_files=['/etc/file1'],
                                      discover_config_files=False):
            assert fname == "config"
            assert f == ConfigFeature(name='file1', content='content',
                                      path='/etc/file1')
        assert args[0].call_count == 1  # lstat

    @mock.patch('utils.config_utils.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('utils.config_utils.os.walk',
                side_effect=lambda p: [
                    ('/', [], ['file1', 'file2', 'file3.conf'])])
    @mock.patch('utils.config_utils.os.path.exists',
                side_effect=lambda p: True)
    @mock.patch('utils.config_utils.os.path.isfile',
                side_effect=lambda p: True)
    @mock.patch('utils.config_utils.os.path.getsize',
                side_effect=lambda p: 1000)
    @mock.patch('utils.config_utils.os.lstat',
                side_effect=mocked_os_lstat)
    @mock.patch('utils.config_utils.codecs.open',
                side_effect=mocked_codecs_open)
    def test_config_host_crawler_with_discover(self, *args):
        fc = ConfigHostCrawler()

        configs = fc.crawl(known_config_files=['/etc/file1'],
                           discover_config_files=True)
        print configs
        assert set(configs) == set([('/file3.conf',
                                     ConfigFeature(name='file3.conf',
                                                   content='content',
                                                   path='/file3.conf'),
                                     'config'),
                                    ('/etc/file1',
                                     ConfigFeature(name='file1',
                                                   content='content',
                                                   path='/etc/file1'),
                                     'config')])

    @mock.patch(
        ("plugins.systems.config_container_crawler."
            "utils.dockerutils.exec_dockerinspect"),
        side_effect=lambda long_id: {'State': {'Pid': 123}})
    @mock.patch(
        'plugins.systems.config_container_crawler.run_as_another_namespace',
        side_effect=mocked_run_as_another_namespace)
    @mock.patch('utils.config_utils.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('utils.config_utils.os.path.exists',
                side_effect=lambda p: True)
    @mock.patch('utils.config_utils.os.lstat',
                side_effect=mocked_os_lstat)
    @mock.patch('utils.config_utils.codecs.open',
                side_effect=mocked_codecs_open)
    def test_config_container_crawler(self, *args):
        fc = ConfigContainerCrawler()
        for (k, f, fname) in fc.crawl(known_config_files=['/etc/file1'],
                                      discover_config_files=False):
            assert fname == "config"
            assert f == ConfigFeature(name='file1', content='content',
                                      path='/etc/file1')
        assert args[0].call_count == 1  # codecs open

    @mock.patch('utils.config_utils.codecs.open',
                side_effect=mocked_codecs_open)
    @mock.patch('utils.config_utils.os.lstat',
                side_effect=mocked_os_lstat)
    @mock.patch(
        ("plugins.systems.config_container_crawler."
            "utils.dockerutils.exec_dockerinspect"),
        side_effect=lambda long_id: {'State': {'Pid': 123}})
    @mock.patch(
        'plugins.systems.config_container_crawler.run_as_another_namespace',
        side_effect=mocked_run_as_another_namespace)
    @mock.patch('utils.config_utils.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('utils.config_utils.os.walk',
                side_effect=lambda p: [
                    ('/', [], ['file1', 'file2', 'file3.conf'])])
    @mock.patch('utils.config_utils.os.path.exists',
                side_effect=lambda p: True)
    @mock.patch('utils.config_utils.os.path.isfile',
                side_effect=lambda p: True)
    @mock.patch('utils.config_utils.os.path.getsize',
                side_effect=lambda p: 1000)
    def test_config_container_crawler_discover(self, *args):
        fc = ConfigContainerCrawler()

        configs = fc.crawl(known_config_files=['/etc/file1'],
                           discover_config_files=True)
        assert set(configs) == set([('/file3.conf',
                                     ConfigFeature(name='file3.conf',
                                                   content='content',
                                                   path='/file3.conf'),
                                     'config'),
                                    ('/etc/file1',
                                     ConfigFeature(name='file1',
                                                   content='content',
                                                   path='/etc/file1'),
                                     'config')])

    @mock.patch(
        ("plugins.systems.config_container_crawler."
            "run_as_another_namespace"),
        side_effect=mocked_run_as_another_namespace)
    @mock.patch(
        ("plugins.systems.config_container_crawler."
            "utils.dockerutils.exec_dockerinspect"),
        side_effect=lambda long_id: {'State': {'Pid': 123}})
    @mock.patch(
        ("plugins.systems.config_container_crawler.utils.dockerutils."
            "get_docker_container_rootfs_path"),
        side_effect=lambda long_id: '/1/2/3')
    @mock.patch('utils.config_utils.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('utils.config_utils.os.path.exists',
                side_effect=lambda p: True)
    @mock.patch('utils.config_utils.os.lstat',
                side_effect=mocked_os_lstat)
    @mock.patch('utils.config_utils.codecs.open',
                side_effect=mocked_codecs_open)
    def test_config_container_crawler_avoidsetns(self, *args):
        fc = ConfigContainerCrawler()
        for (k, f, fname) in fc.crawl(known_config_files=['/etc/file1'],
                                      discover_config_files=False,
                                      avoid_setns=True):
            assert fname == "config"
            assert f == ConfigFeature(name='file1', content='content',
                                      path='/etc/file1')
        assert args[0].call_count == 1  # lstat

    @mock.patch(
        ("plugins.systems.config_container_crawler."
            "run_as_another_namespace"),
        side_effect=mocked_run_as_another_namespace)
    @mock.patch(
        ("plugins.systems.config_container_crawler."
            "utils.dockerutils.exec_dockerinspect"),
        side_effect=lambda long_id: {'State': {'Pid': 123}})
    @mock.patch(
        ("plugins.systems.config_container_crawler.utils.dockerutils."
            "get_docker_container_rootfs_path"),
        side_effect=lambda long_id: '/1/2/3')
    @mock.patch('utils.config_utils.os.path.isdir',
                side_effect=lambda p: True)
    @mock.patch('utils.config_utils.os.walk',
                side_effect=lambda p: [
                    ('/', [], ['file1', 'file2', 'file3.conf'])])
    @mock.patch('utils.config_utils.os.path.exists',
                side_effect=lambda p: True)
    @mock.patch('utils.config_utils.os.path.isfile',
                side_effect=lambda p: True)
    @mock.patch('utils.config_utils.os.path.getsize',
                side_effect=lambda p: 1000)
    @mock.patch('utils.config_utils.os.lstat',
                side_effect=mocked_os_lstat)
    @mock.patch('utils.config_utils.codecs.open',
                side_effect=mocked_codecs_open)
    def test_config_container_crawler_avoidsetns_discover(self, *args):
        fc = ConfigContainerCrawler()
        configs = fc.crawl(known_config_files=['/etc/file1'],
                           avoid_setns=True,
                           discover_config_files=True)
        assert set(configs) == set([('/file3.conf',
                                     ConfigFeature(name='file3.conf',
                                                   content='content',
                                                   path='/file3.conf'),
                                     'config'),
                                    ('/etc/file1',
                                     ConfigFeature(name='file1',
                                                   content='content',
                                                   path='/etc/file1'),
                                     'config')])

    @mock.patch(
        'utils.package_utils.osinfo.get_osinfo',
        side_effect=lambda mount_point=None: {
            'os': 'ubuntu',
            'version': '123'})
    @mock.patch('utils.package_utils.os.path.exists',
                side_effect=lambda p: True)
    @mock.patch('utils.package_utils.get_dpkg_packages',
                side_effect=lambda a, b, c: [('pkg1',
                                              PackageFeature(None, 'pkg1',
                                                             123, 'v1',
                                                             'x86'))])
    def test_package_host_crawler_dpkg(self, *args):
        fc = PackageHostCrawler()
        for (k, f, fname) in fc.crawl():
            assert fname == "package"
            assert f == PackageFeature(
                installed=None,
                pkgname='pkg1',
                pkgsize=123,
                pkgversion='v1',
                pkgarchitecture='x86')
        assert args[0].call_count == 1
        args[0].assert_called_with('/', 'var/lib/dpkg', 0)

    @mock.patch(
        'utils.package_utils.osinfo.get_osinfo',
        side_effect=lambda mount_point=None: {
            'os': 'ubuntu',
            'version': '123'})
    @mock.patch('utils.package_utils.os.path.exists',
                side_effect=lambda p: True)
    @mock.patch('utils.package_utils.get_dpkg_packages',
                side_effect=throw_os_error)
    def test_package_host_crawler_dpkg_failure(self, *args):
        fc = PackageHostCrawler()
        with self.assertRaises(CrawlError):
            for (k, f, fname) in fc.crawl():
                pass
        assert args[0].call_count == 1
        args[0].assert_called_with('/', 'var/lib/dpkg', 0)

    @mock.patch(
        'utils.package_utils.osinfo.get_osinfo',
        side_effect=lambda mount_point=None: {
            'os': 'redhat',
            'version': '123'})
    @mock.patch('utils.package_utils.os.path.exists',
                side_effect=lambda p: True)
    @mock.patch('utils.package_utils.get_rpm_packages',
                side_effect=lambda a, b, c, d: [('pkg1',
                                                 PackageFeature(None, 'pkg1',
                                                                123, 'v1',
                                                                'x86'))])
    def test_package_host_crawler_rpm(self, *args):
        fc = PackageHostCrawler()
        for (k, f, fname) in fc.crawl():
            assert fname == "package"
            assert f == PackageFeature(
                installed=None,
                pkgname='pkg1',
                pkgsize=123,
                pkgversion='v1',
                pkgarchitecture='x86')
        assert args[0].call_count == 1
        args[0].assert_called_with('/', 'var/lib/rpm', 0, False)

    @mock.patch(
        ("plugins.systems.package_container_crawler."
            "exec_dockerinspect"),
        side_effect=lambda long_id: {'State': {'Pid': 123}})
    @mock.patch(
        'utils.package_utils.osinfo.get_osinfo',
        side_effect=lambda mount_point=None: {
            'os': 'ubuntu',
            'version': '123'})
    @mock.patch(
        'plugins.systems.package_container_crawler.run_as_another_namespace',
        side_effect=mocked_run_as_another_namespace)
    @mock.patch('utils.package_utils.os.path.exists',
                side_effect=lambda p: True)
    @mock.patch('utils.package_utils.get_dpkg_packages',
                side_effect=lambda a, b, c: [('pkg1',
                                              PackageFeature(None, 'pkg1',
                                                             123, 'v1',
                                                             'x86'))])
    def test_package_container_crawler_dpkg(self, *args):
        fc = PackageContainerCrawler()
        for (k, f, fname) in fc.crawl():
            assert fname == "package"
            assert f == PackageFeature(
                installed=None,
                pkgname='pkg1',
                pkgsize=123,
                pkgversion='v1',
                pkgarchitecture='x86')
        assert args[0].call_count == 1
        args[0].assert_called_with('/', 'var/lib/dpkg', 0)

    @mock.patch(
        ("plugins.systems.package_container_crawler."
            "exec_dockerinspect"),
        side_effect=lambda long_id: {'State': {'Pid': 123}})
    @mock.patch(
        'plugins.systems.package_container_crawler.run_as_another_namespace',
        side_effect=mocked_run_as_another_namespace)
    @mock.patch(
        ("plugins.systems.package_container_crawler."
            "get_docker_container_rootfs_path"),
        side_effect=lambda long_id: '/a/b/c')
    @mock.patch(
        'utils.package_utils.osinfo.get_osinfo',
        side_effect=lambda mount_point=None: {
            'os': 'ubuntu',
            'version': '123'})
    @mock.patch('utils.package_utils.os.path.exists',
                side_effect=lambda p: True if 'dpkg' in p else False)
    @mock.patch('utils.package_utils.get_dpkg_packages',
                side_effect=throw_os_error)
    def test_package_container_crawler_dpkg_failure(self, *args):
        fc = PackageContainerCrawler()
        with self.assertRaises(CrawlError):
            for (k, f, fname) in fc.crawl():
                pass
        # get_dpkg_packages is called a second time after the first failure.
        # first time is OUTCONTAINER mode with setns
        # second time is OUTCONTAINER mode with avoid_setns
        assert args[0].call_count == 2
        args[0].assert_called_with('/a/b/c', 'var/lib/dpkg', 0)
        args[2].assert_called_with(mount_point='/a/b/c')  # get_osinfo()

    @mock.patch(
        ("plugins.systems.package_container_crawler."
            "exec_dockerinspect"),
        side_effect=lambda long_id: {'State': {'Pid': 123}})
    @mock.patch(
        'plugins.systems.package_container_crawler.run_as_another_namespace',
        side_effect=mocked_run_as_another_namespace)
    @mock.patch(
        ("plugins.systems.package_container_crawler."
            "get_docker_container_rootfs_path"),
        side_effect=lambda long_id: '/a/b/c')
    @mock.patch(
        'utils.package_utils.osinfo.get_osinfo',
        side_effect=lambda mount_point=None: {
            'os': 'redhat',
            'version': '123'})
    @mock.patch('utils.package_utils.os.path.exists',
                side_effect=lambda p: True if 'rpm' in p else False)
    @mock.patch('utils.package_utils.get_rpm_packages',
                side_effect=throw_os_error)
    def test_package_container_crawler_rpm_failure(self, *args):
        fc = PackageContainerCrawler()
        with self.assertRaises(CrawlError):
            for (k, f, fname) in fc.crawl():
                pass
        # get_dpkg_packages is called a second time after the first failure.
        # first time is OUTCONTAINER mode with setns
        # second time is OUTCONTAINER mode with avoid_setns
        assert args[0].call_count == 2
        args[0].assert_called_with('/a/b/c', 'var/lib/rpm', 0, True)
        args[2].assert_called_with(mount_point='/a/b/c')  # get_osinfo()

    @mock.patch(
        ("plugins.systems.package_container_crawler."
            "exec_dockerinspect"),
        side_effect=lambda long_id: {'State': {'Pid': 123}})
    @mock.patch(
        ("plugins.systems.package_container_crawler."
            "get_docker_container_rootfs_path"),
        side_effect=lambda long_id: '/a/b/c')
    @mock.patch(
        'utils.package_utils.osinfo.get_osinfo',
        side_effect=lambda mount_point=None: {
            'os': 'ubuntu',
            'version': '123'})
    @mock.patch('utils.package_utils.os.path.exists',
                side_effect=lambda p: True)
    @mock.patch('utils.package_utils.get_dpkg_packages',
                side_effect=lambda a, b, c: [('pkg1',
                                              PackageFeature(None, 'pkg1',
                                                             123, 'v1',
                                                             'x86'))])
    def test_package_container_crawler_avoidsetns(self, *args):
        fc = PackageContainerCrawler()
        for (k, f, fname) in fc.crawl(avoid_setns=True):
            assert fname == "package"
            assert f == PackageFeature(
                installed=None,
                pkgname='pkg1',
                pkgsize=123,
                pkgversion='v1',
                pkgarchitecture='x86')
        assert args[0].call_count == 1

    @mock.patch('plugins.systems.process_host_crawler.psutil.process_iter',
                side_effect=lambda: [Process('init')])
    def test_process_host_crawler(self, *args):
        fc = ProcessHostCrawler()
        for (k, f, fname) in fc.crawl():
            print f
            assert fname == "process"
            assert f.pname == 'init'
            assert f.cmd == 'cmd'
            assert f.pid == 123
        assert args[0].call_count == 1

    @mock.patch(
        ("plugins.systems.process_container_crawler.utils.dockerutils."
         "exec_dockerinspect"),
        side_effect=lambda long_id: {'State': {'Pid': 123}})
    @mock.patch(
        'plugins.systems.process_container_crawler.psutil.process_iter',
        side_effect=lambda: [Process('init')])
    @mock.patch(
        'plugins.systems.process_container_crawler.run_as_another_namespace',
        side_effect=mocked_run_as_another_namespace)
    def test_process_container_crawler(self, *args):
        fc = ProcessContainerCrawler()
        for (k, f, fname) in fc.crawl('123'):
            print f
            assert fname == "process"
            assert f.pname == 'init'
            assert f.cmd == 'cmd'
            assert f.pid == 123
        assert args[0].call_count == 1

    @mock.patch('plugins.systems.process_vm_crawler.psvmi.context_init',
                side_effect=lambda dn1, dn2, kv, d, a: 1000)
    @mock.patch('plugins.systems.process_vm_crawler.psvmi.process_iter',
                side_effect=lambda vmc: [Process('init')])
    @mock.patch('plugins.systems.process_vm_crawler.psvmi')
    def test_process_vm_crawler(self, *args):
        fc = process_vm_crawler()
        for (k, f, fname) in fc.crawl(vm_desc=('dn', '2.6', 'ubuntu', 'x86')):
            print f
            assert fname == "process"
            assert f.pname == 'init'
            assert f.cmd == 'cmd'
            assert f.pid == 123
        assert args[1].call_count == 1  # process_iter

    @mock.patch('utils.disk_utils.psutil.disk_partitions',
                side_effect=mocked_disk_partitions)
    @mock.patch('utils.disk_utils.psutil.disk_usage',
                side_effect=lambda x: pdiskusage(10, 100))
    def test_crawl_disk_partitions_invm_mode(self, *args):
        fc = DiskHostCrawler()
        disks = fc.crawl()
        assert set(disks) == set([('/a',
                                   DiskFeature(partitionname='/dev/a',
                                               freepct=90.0,
                                               fstype='type',
                                               mountpt='/a',
                                               mountopts='opts',
                                               partitionsize=100),
                                   'disk'),
                                  ('/b',
                                   DiskFeature(partitionname='/dev/b',
                                               freepct=90.0,
                                               fstype='type',
                                               mountpt='/b',
                                               mountopts='opts',
                                               partitionsize=100),
                                   'disk')])

    @mock.patch(
        'plugins.systems.disk_container_crawler.run_as_another_namespace',
        side_effect=mocked_run_as_another_namespace)
    @mock.patch('utils.disk_utils.psutil.disk_partitions',
                side_effect=mocked_disk_partitions)
    @mock.patch('utils.disk_utils.psutil.disk_usage',
                side_effect=lambda x: pdiskusage(10, 100))
    @mock.patch(
        ("plugins.systems.disk_container_crawler.utils.dockerutils."
         "exec_dockerinspect"),
        side_effect=lambda long_id: {'State': {'Pid': 123}})
    def test_crawl_disk_partitions_outcontainer_mode(self, *args):
        fc = DiskContainerCrawler()
        disks = fc.crawl('123')
        assert set(disks) == set([('/a',
                                   DiskFeature(partitionname='/dev/a',
                                               freepct=90.0,
                                               fstype='type',
                                               mountpt='/a',
                                               mountopts='opts',
                                               partitionsize=100),
                                   'disk'),
                                  ('/b',
                                   DiskFeature(partitionname='/dev/b',
                                               freepct=90.0,
                                               fstype='type',
                                               mountpt='/b',
                                               mountopts='opts',
                                               partitionsize=100),
                                   'disk')])

    @mock.patch('utils.metric_utils.psutil.process_iter',
                side_effect=lambda: [Process('init')])
    def test_crawl_metrics_invm_mode(self, *args):
        fc = MetricHostCrawler()
        for (k, f, t) in fc.crawl():
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

    @mock.patch('utils.metric_utils.psutil.process_iter',
                side_effect=lambda: [Process('init')])
    @mock.patch('utils.metric_utils.round',
                side_effect=throw_os_error)
    def test_crawl_metrics_invm_mode_failure(self, *args):
        with self.assertRaises(OSError):
            fc = MetricHostCrawler()
            for ff in fc.crawl():
                pass
        assert args[0].call_count == 1

    @mock.patch('utils.metric_utils.psutil.process_iter',
                side_effect=lambda: [Process('init')])
    @mock.patch(
        'plugins.systems.metric_container_crawler.run_as_another_namespace',
        side_effect=mocked_run_as_another_namespace)
    @mock.patch(
        ("plugins.systems.disk_container_crawler.utils.dockerutils."
         "exec_dockerinspect"),
        side_effect=lambda long_id: {'State': {'Pid': 123}})
    def test_crawl_metrics_outcontainer_mode(self, *args):
        fc = MetricContainerCrawler()
        for (k, f, t) in fc.crawl('123'):
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

    @mock.patch('plugins.systems.metric_vm_crawler.psvmi.context_init',
                side_effect=lambda dn1, dn2, kv, d, a: 1000)
    @mock.patch('plugins.systems.metric_vm_crawler.psvmi.process_iter',
                side_effect=lambda vmc: [Process('init')])
    @mock.patch(
        ("plugins.systems.metric_vm_crawler."
         "MetricVmCrawler._crawl_metrics_cpu_percent"),
        side_effect=lambda proc: 30.0)
    @mock.patch('plugins.systems.metric_vm_crawler.psvmi')
    def test_crawl_metrics_vm_mode(self, *args):
        fc = MetricVmCrawler()
        for (k, f, t) in fc.crawl(vm_desc=('dn', '2.6', 'ubuntu', 'x86')):
            assert f.cpupct == 30.0
            assert f.mempct == 30.0
            assert f.pname == 'init'
            assert f.pid == 123
            assert f.rss == 10
            assert f.status == 'Running'
            assert f.vms == 20
            assert f.read == 10
            assert f.write == 20
        assert args[1].call_count == 1  # process_iter

    @mock.patch('utils.connection_utils.psutil.process_iter',
                side_effect=lambda: [Process('init')])
    def test_crawl_connections_invm_mode(self, *args):
        fc = ConnectionHostCrawler()
        for (k, f, t) in fc.crawl():
            assert f.localipaddr == '1.1.1.1'
            assert f.remoteipaddr == '2.2.2.2'
            assert f.localport == '22'
            assert f.remoteport == '22'
        assert args[0].call_count == 1

    @mock.patch('utils.connection_utils.psutil.process_iter',
                side_effect=lambda: [Process('init')])
    @mock.patch(
        'plugins.systems.connection_container_crawler.run_as_another_namespace',
        side_effect=mocked_run_as_another_namespace)
    @mock.patch(
        ("plugins.systems.connection_container_crawler.utils.dockerutils."
         "exec_dockerinspect"),
        side_effect=lambda long_id: {'State': {'Pid': 123}})
    def test_crawl_connections_outcontainer_mode(self, *args):
        fc = ConnectionContainerCrawler()
        for (k, f, t) in fc.crawl('123'):
            assert f.localipaddr == '1.1.1.1'
            assert f.remoteipaddr == '2.2.2.2'
            assert f.localport == '22'
            assert f.remoteport == '22'
        assert args[0].call_count == 1

    @mock.patch('plugins.systems.connection_vm_crawler.psvmi.context_init',
                side_effect=lambda dn1, dn2, kv, d, a: 1000)
    @mock.patch('plugins.systems.connection_vm_crawler.psvmi.process_iter',
                side_effect=lambda vmc: [Process('init')])
    @mock.patch('plugins.systems.connection_vm_crawler.psvmi')
    def test_crawl_connections_outvm_mode(self, *args):
        fc = ConnectionVmCrawler()
        for (k, f, t) in fc.crawl(vm_desc=('dn', '2.6', 'ubuntu', 'x86')):
            assert f.localipaddr == '1.1.1.1'
            assert f.remoteipaddr == '2.2.2.2'
            assert f.localport == '22'
            assert f.remoteport == '22'
        assert args[1].call_count == 1

    @mock.patch('plugins.systems.memory_host_crawler.psutil.virtual_memory',
                side_effect=lambda: psutils_memory(2, 2, 3, 4))
    def test_crawl_memory_invm_mode(self, *args):
        fc = MemoryHostCrawler()
        for (k, f, t) in fc.crawl():
            assert f == MemoryFeature(
                memory_used=2,
                memory_buffered=3,
                memory_cached=4,
                memory_free=2,
                memory_util_percentage=50)
        assert args[0].call_count == 1

    @mock.patch('plugins.systems.memory_host_crawler.psutil.virtual_memory',
                side_effect=throw_os_error)
    def test_crawl_memory_invm_mode_failure(self, *args):
        fc = MemoryHostCrawler()
        with self.assertRaises(OSError):
            for (k, f, t) in fc.crawl():
                pass
        assert args[0].call_count == 1

    @mock.patch('plugins.systems.memory_vm_crawler.psvmi.context_init',
                side_effect=lambda dn1, dn2, kv, d, a: 1000)
    @mock.patch('plugins.systems.memory_vm_crawler.psvmi.system_memory_info',
                side_effect=lambda vmc: psvmi_memory(10, 20, 30, 40))
    @mock.patch('plugins.systems.memory_vm_crawler.psvmi')
    def test_crawl_memory_outvm_mode(self, *args):
        fc = MemoryVmCrawler()
        for (k, f, t) in fc.crawl(vm_desc=('dn', '2.6', 'ubuntu', 'x86')):
            assert f == MemoryFeature(
                memory_used=10,
                memory_buffered=20,
                memory_cached=30,
                memory_free=40,
                memory_util_percentage=20)
        assert args[1].call_count == 1

    @mock.patch(
        'plugins.systems.memory_container_crawler.psutil.virtual_memory',
        side_effect=lambda: psutils_memory(
            10,
            10,
            3,
            10))
    @mock.patch('plugins.systems.memory_container_crawler.open',
                side_effect=mocked_memory_cgroup_open)
    @mock.patch('plugins.systems.memory_container_crawler.DockerContainer',
                side_effect=lambda container_id: DummyContainer(container_id))
    def test_crawl_memory_outcontainer_mode(self, *args):
        fc = MemoryContainerCrawler()
        for (k, f, t) in fc.crawl('123'):
            assert f == MemoryFeature(
                memory_used=2,
                memory_buffered=200,
                memory_cached=100,
                memory_free=0,
                memory_util_percentage=100)
        assert args[1].call_count == 3  # 3 cgroup files

    @mock.patch(
        'plugins.systems.memory_container_crawler.psutil.virtual_memory',
        side_effect=lambda: psutils_memory(
            10,
            10,
            3,
            10))
    @mock.patch('plugins.systems.memory_container_crawler.open',
                side_effect=throw_os_error)
    @mock.patch('plugins.systems.memory_container_crawler.DockerContainer',
                side_effect=lambda container_id: DummyContainer(container_id))
    def test_crawl_memory_outcontainer_mode_failure(self, *args):
        fc = MemoryContainerCrawler()
        with self.assertRaises(OSError):
            for (k, f, t) in fc.crawl('123'):
                pass
        assert args[1].call_count == 1  # 1 cgroup files

    @mock.patch(
        'plugins.systems.cpu_host_crawler.psutil.cpu_times_percent',
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
        fc = CpuHostCrawler()
        for (k, f, t) in fc.crawl():
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

    @mock.patch('plugins.systems.cpu_host_crawler.psutil.cpu_times_percent',
                side_effect=throw_os_error)
    def test_crawl_cpu_invm_mode_failure(self, *args):
        fc = CpuHostCrawler()
        with self.assertRaises(OSError):
            for (k, f, t) in fc.crawl():
                pass
        assert args[0].call_count == 1

    @mock.patch(
        'plugins.systems.cpu_container_crawler.psutil.cpu_times_percent',
        side_effect=lambda percpu: [
            psutils_cpu(
                10,
                20,
                30,
                40,
                50,
                60,
                70)])
    @mock.patch('plugins.systems.cpu_container_crawler.time.sleep')
    @mock.patch('plugins.systems.cpu_container_crawler.open',
                side_effect=mocked_cpu_cgroup_open)
    @mock.patch('plugins.systems.cpu_container_crawler.DockerContainer',
                side_effect=lambda container_id: DummyContainer(container_id))
    def test_crawl_cpu_outcontainer_mode(self, *args):
        fc = CpuContainerCrawler()
        for (k, f, t) in fc.crawl('123'):
            assert f == CpuFeature(
                cpu_idle=90.0,
                cpu_nice=20,
                cpu_user=5.0,
                cpu_wait=40,
                cpu_system=5.0,
                cpu_interrupt=60,
                cpu_steal=70,
                cpu_util=10.0)
        assert args[1].call_count == 3  # open for 3 cgroup files

    @mock.patch(
        'plugins.systems.cpu_container_crawler.psutil.cpu_times_percent',
        side_effect=lambda percpu: [
            psutils_cpu(
                10,
                20,
                30,
                40,
                50,
                60,
                70)])
    @mock.patch('plugins.systems.cpu_container_crawler.time.sleep')
    @mock.patch('plugins.systems.cpu_container_crawler.open',
                side_effect=throw_os_error)
    @mock.patch('plugins.systems.cpu_container_crawler.DockerContainer',
                side_effect=lambda container_id: DummyContainer(container_id))
    def test_crawl_cpu_outcontainer_mode_failure(self, *args):
        fc = CpuContainerCrawler()
        with self.assertRaises(OSError):
            for (k, f, t) in fc.crawl('123'):
                pass
        assert args[0].call_count == 1

    @mock.patch(
        'plugins.systems.interface_host_crawler.psutil.net_io_counters',
        side_effect=lambda pernic: {'interface1-unit-tests':
                                    psutils_net(
                                        10,
                                        20,
                                        30,
                                        40,
                                        50,
                                        60)})
    def test_crawl_interface_invm_mode(self, *args):
        fc = InterfaceHostCrawler()
        for (k, f, t) in fc.crawl():
            assert f == InterfaceFeature(
                if_octets_tx=0,
                if_octets_rx=0,
                if_packets_tx=0,
                if_packets_rx=0,
                if_errors_tx=0,
                if_errors_rx=0)

        for (k, f, t) in fc.crawl():
            assert f == InterfaceFeature(
                if_octets_tx=0,
                if_octets_rx=0,
                if_packets_tx=0,
                if_packets_rx=0,
                if_errors_tx=0,
                if_errors_rx=0)
        assert args[0].call_count == 2

    @mock.patch(
        'plugins.systems.interface_host_crawler.psutil.net_io_counters',
        side_effect=throw_os_error)
    def test_crawl_interface_invm_mode_failure(self, *args):
        fc = InterfaceHostCrawler()
        with self.assertRaises(OSError):
            for (k, f, t) in fc.crawl():
                pass

        # Each crawl in crawlutils.py instantiates a FeaturesCrawler object
        with self.assertRaises(OSError):
            for (k, f, t) in fc.crawl():
                pass
        assert args[0].call_count == 2

    @mock.patch('plugins.systems.interface_container_crawler.DockerContainer',
                side_effect=lambda container_id: DummyContainer(container_id))
    @mock.patch(
        'plugins.systems.interface_container_crawler.run_as_another_namespace',
        side_effect=mocked_run_as_another_namespace)
    @mock.patch(
        'plugins.systems.interface_container_crawler.psutil.net_io_counters',
        side_effect=lambda pernic: {'eth0':
                                    psutils_net(
                                        10,
                                        20,
                                        30,
                                        40,
                                        50,
                                        60)})
    def test_crawl_interface_outcontainer_mode(self, *args):
        fc = InterfaceContainerCrawler()
        for (k, f, t) in fc.crawl('123'):
            assert f == InterfaceFeature(
                if_octets_tx=0,
                if_octets_rx=0,
                if_packets_tx=0,
                if_packets_rx=0,
                if_errors_tx=0,
                if_errors_rx=0)

        for (k, f, t) in fc.crawl('123'):
            assert f == InterfaceFeature(
                if_octets_tx=0,
                if_octets_rx=0,
                if_packets_tx=0,
                if_packets_rx=0,
                if_errors_tx=0,
                if_errors_rx=0)
        assert args[0].call_count == 2
        assert args[1].call_count == 2

    @mock.patch('plugins.systems.interface_vm_crawler.psvmi.context_init',
                side_effect=lambda dn1, dn2, kv, d, a: 1000)
    @mock.patch('plugins.systems.interface_vm_crawler.psvmi.interface_iter',
                side_effect=lambda vmc: [psvmi_interface(
                    'eth1', 10, 20, 30, 40, 50, 60)])
    @mock.patch('plugins.systems.interface_vm_crawler.psvmi')
    def test_crawl_interface_outvm_mode(self, *args):
        fc = InterfaceVmCrawler()
        for (k, f, t) in fc.crawl(vm_desc=('dn', '2.6', 'ubuntu', 'x86')):
            assert f == InterfaceFeature(
                if_octets_tx=0,
                if_octets_rx=0,
                if_packets_tx=0,
                if_packets_rx=0,
                if_errors_tx=0,
                if_errors_rx=0)

        for (k, f, t) in fc.crawl(vm_desc=('dn', '2.6', 'ubuntu', 'x86')):
            assert f == InterfaceFeature(
                if_octets_tx=0,
                if_octets_rx=0,
                if_packets_tx=0,
                if_packets_rx=0,
                if_errors_tx=0,
                if_errors_rx=0)
        assert args[1].call_count == 2
        assert args[2].call_count == 2

    @mock.patch('plugins.systems.load_host_crawler.os.getloadavg',
                side_effect=lambda: [1, 2, 3])
    def test_crawl_load_invm_mode(self, *args):
        fc = LoadHostCrawler()
        for (k, f, t) in fc.crawl():
            assert f == LoadFeature(shortterm=1, midterm=2, longterm=2)
        assert args[0].call_count == 1

    @mock.patch('plugins.systems.load_host_crawler.os.getloadavg',
                side_effect=throw_os_error)
    def test_crawl_load_invm_mode_failure(self, *args):
        fc = LoadHostCrawler()
        with self.assertRaises(OSError):
            for (k, f, t) in fc.crawl():
                pass
        assert args[0].call_count == 1

    @mock.patch(
        'plugins.systems.load_container_crawler.run_as_another_namespace',
        side_effect=mocked_run_as_another_namespace)
    @mock.patch('plugins.systems.load_container_crawler.os.getloadavg',
                side_effect=lambda: [1, 2, 3])
    @mock.patch('plugins.systems.load_container_crawler.DockerContainer',
                side_effect=lambda container_id: DummyContainer(container_id))
    def test_crawl_load_outcontainer_mode(self, *args):
        fc = LoadContainerCrawler()
        for (k, f, t) in fc.crawl('123'):
            assert f == LoadFeature(shortterm=1, midterm=2, longterm=2)
        assert args[1].call_count == 1
        assert args[2].call_count == 1

    @mock.patch('plugins.systems.dockerps_host_crawler.exec_dockerps',
                side_effect=lambda: [{'State': {'Running': True},
                                      'Image': 'reg/image:latest',
                                      'Config': {'Cmd': 'command'},
                                      'Name': 'name',
                                      'Id': 'id'}])
    def test_crawl_dockerps_invm_mode(self, *args):
        fc = DockerpsHostCrawler()
        for (k, f, t) in fc.crawl():
            assert f == DockerPSFeature(
                Status=True,
                Created=0,
                Image='reg/image:latest',
                Ports=[],
                Command='command',
                Names='name',
                Id='id')
        assert args[0].call_count == 1

    @mock.patch('plugins.systems.dockerps_host_crawler.exec_dockerps',
                side_effect=throw_os_error)
    def test_crawl_dockerps_invm_mode_failure(self, *args):
        fc = DockerpsHostCrawler()
        with self.assertRaises(OSError):
            for (k, f, t) in fc.crawl():
                pass
        assert args[0].call_count == 1

    @mock.patch('plugins.systems.dockerhistory_container_crawler.exec_docker_history',
                side_effect=lambda long_id: [
                    {'Id': 'image1', 'random': 'abc'},
                    {'Id': 'image2', 'random': 'abc'}])
    def test_crawl_dockerhistory_outcontainer_mode(self, *args):
        fc = DockerhistoryContainerCrawler()
        for (k, f, t) in fc.crawl('123'):
            assert f == {'history': [{'Id': 'image1', 'random': 'abc'},
                                     {'Id': 'image2', 'random': 'abc'}]}
        assert args[0].call_count == 1

    @mock.patch(
        'plugins.systems.dockerhistory_container_crawler.exec_docker_history',
        side_effect=throw_os_error)
    def test_crawl_dockerhistory_outcontainer_mode_failure(self, *args):
        fc = DockerhistoryContainerCrawler()
        with self.assertRaises(OSError):
            for (k, f, t) in fc.crawl('123'):
                pass
        assert args[0].call_count == 1

    @mock.patch(
        'plugins.systems.dockerinspect_container_crawler.exec_dockerinspect',
        side_effect=lambda long_id: {
            'Id': 'image1',
            'random': 'abc'})
    def test_crawl_dockerinspect_outcontainer_mode(self, *args):
        fc = DockerinspectContainerCrawler()
        for (k, f, t) in fc.crawl('123'):
            assert f == {'Id': 'image1', 'random': 'abc'}
        assert args[0].call_count == 1

    @mock.patch(
        'plugins.systems.dockerinspect_container_crawler.exec_dockerinspect',
        side_effect=throw_os_error)
    def test_crawl_dockerinspect_outcontainer_mode_failure(self, *args):
        fc = DockerinspectContainerCrawler()
        with self.assertRaises(OSError):
            for (k, f, t) in fc.crawl('123'):
                pass
        assert args[0].call_count == 1
