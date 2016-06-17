#!/usr/bin/python
# -*- coding: utf-8 -*-

import platform
import os
import stat
import logging
import codecs
import subprocess
import tempfile
import shutil
import fnmatch
import re
import time
import cPickle as pickle

# Additional modules

import platform_outofband

# External dependencies that must be pip install'ed separately

import psutil

from namespace import run_as_another_namespace, ALL_NAMESPACES
from crawler_exceptions import CrawlError
import dockerutils
from features import (OSFeature, FileFeature, ConfigFeature, DiskFeature,
                      ProcessFeature, MetricFeature, ConnectionFeature,
                      PackageFeature, MemoryFeature, CpuFeature,
                      InterfaceFeature, LoadFeature, DockerPSFeature,
                      DockerHistoryFeature)
import misc
from crawlmodes import Modes
from package_utils import get_rpm_packages, get_dpkg_packages


logger = logging.getLogger('crawlutils')


FEATURE_SCHEMA = {
    'os': OSFeature._fields,
    'file': FileFeature._fields,
    'config': ConfigFeature._fields,
    'disk': DiskFeature._fields,
    'process': ProcessFeature._fields,
    'connection': ConnectionFeature._fields,
    'metric': MetricFeature._fields,
    'package': PackageFeature._fields,
    'memory': MemoryFeature._fields,
    'cpu': CpuFeature._fields,
    'interface': InterfaceFeature._fields,
    'load': LoadFeature._fields,
    'dockerps': DockerPSFeature._fields,
    'dockerhistory': DockerHistoryFeature._fields,
}


class FeaturesCrawler:

    """This class abstracts the actual crawling functionality like getting the
    list of running processes, or listing the installed packages. This class is
    instantiated for every frame. A frame is created and emited for every
    container and at every crawling interval.
    """

    @staticmethod
    def get_feature_schema():
        return FEATURE_SCHEMA

    # feature_epoch must be a UTC timestamp. If > 0 only features
    # accessed/modified/created since this time are crawled

    def __init__(
        self,
        feature_epoch=0,
        config_file_discovery_heuristic=None,
        crawl_mode=Modes.INVM,
        vm=None,
        namespace=None,
        container=None,
    ):

        saved_args = locals()
        logger.debug('FeaturesCrawler: %s' % (saved_args))
        self.feature_epoch = feature_epoch
        self.is_config_file = config_file_discovery_heuristic \
            or FeaturesCrawler._is_config_file

        self.crawl_mode = crawl_mode

        # Used for OUTCONTAINER crawl mode

        self.container = container
        self.namespace = namespace

    """
    To calculate rates like packages sent per second, we need to
    store the last measurement. We store it in this dictionary.
    """
    _cached_values = {}

    # FIXME Clean the old values!
    @staticmethod
    def _cache_put_value(key, value):
        FeaturesCrawler._cached_values[key] = (value, time.time())

    @staticmethod
    def _cache_get_value(key):
        if key in FeaturesCrawler._cached_values:
            return FeaturesCrawler._cached_values[key]
        else:
            return (None, None)

    # crawl the OS information
    # mountpoint only used for out-of-band crawling

    def crawl_os(self, mountpoint=None, avoid_setns=False):
        if not (avoid_setns and self.crawl_mode == Modes.OUTCONTAINER):
            for (key, feature) in self._crawl_wrapper(
                    self._crawl_os, ALL_NAMESPACES, mountpoint):
                yield (key, feature)
        else:
            mountpoint = dockerutils.get_docker_container_rootfs_path(
                             self.container.long_id)
            self.crawl_mode = Modes.MOUNTPOINT
            try:
                for (key, feature) in self._crawl_os(mountpoint):
                    yield (key, feature)
            finally:
                self.crawl_mode = Modes.OUTCONTAINER


    def _crawl_os(self, mountpoint=None):

        assert(self.crawl_mode is not Modes.OUTCONTAINER)

        logger.debug('Crawling OS')
        if self.crawl_mode == Modes.INVM:
            logger.debug('Using in-VM state information (crawl mode: ' +
                         self.crawl_mode + ')')
            feature_key = platform.system().lower()

            try:
                ips = misc.get_host_ip4_addresses()
            except Exception as e:
                ips = 'unknown'
            try:
                distro = platform.linux_distribution()[0]
            except Exception as e:
                distro = 'unknown'
            try:
                osname = platform.platform()
            except Exception as e:
                osname = 'unknown'

            boot_time = (
                psutil.boot_time() if hasattr(
                    psutil, 'boot_time') else psutil.BOOT_TIME)
            uptime = int(time.time()) - boot_time
            feature_attributes = OSFeature(
                boot_time,
                uptime,
                ips,
                distro,
                osname,
                platform.machine(),
                platform.release(),
                platform.system().lower(),
                platform.version(),
            )
        elif self.crawl_mode == Modes.MOUNTPOINT:
            logger.debug('Using disk image information (crawl mode: ' +
                         self.crawl_mode + ')')
            feature_key = \
                platform_outofband.system(prefix=mountpoint).lower()
            feature_attributes = OSFeature(  # boot time unknown for img
                                             # live IP unknown for img
                'unsupported',
                'unsupported',
                '0.0.0.0',
                platform_outofband.linux_distribution(
                    prefix=mountpoint)[0],
                platform_outofband.platform(prefix=mountpoint),
                platform_outofband.machine(prefix=mountpoint),
                platform_outofband.release(prefix=mountpoint),
                platform_outofband.system(prefix=mountpoint).lower(),
                platform_outofband.version(prefix=mountpoint),
            )
        elif self.crawl_mode == Modes.OUTVM:

            (domain_name, kernel_version, distro, arch) = self.vm
            from psvmi import system_info
            sys = system_info(domain_name, kernel_version, distro, arch)
            uptime = int(time.time()) - sys.boottime
            feature_attributes = OSFeature(
                sys.boottime,
                sys.ipaddr,
                sys.osdistro,
                sys.osname,
                sys.osplatform,
                sys.osrelease,
                sys.ostype,
                sys.osversion,
            )
            feature_key = sys.ostype
        else:
            raise NotImplementedError()
        try:
            yield (feature_key, feature_attributes)
        except Exception as e:
            logger.error('Error crawling OS', exc_info=True)
            raise CrawlError(e)

    # crawl the directory hierarchy under root_dir
    def crawl_files(
        self,
        root_dir='/',
        exclude_dirs=['proc', 'mnt', 'dev', 'tmp'],
        root_dir_alias=None,
        avoid_setns=False,
    ):

        if not (avoid_setns and self.crawl_mode == Modes.OUTCONTAINER):
            for (key, feature) in self._crawl_wrapper(
                    self._crawl_files,
                    ['mnt'],
                    root_dir,
                    exclude_dirs,
                    root_dir_alias):
                yield (key, feature)
        else:
            root_dir = dockerutils.get_docker_container_rootfs_path(
                             self.container.long_id)
            for (key, feature) in self._crawl_files(
                    root_dir,
                    exclude_dirs,
                    root_dir_alias):
                yield (key, feature)


    def _crawl_files(
        self,
        root_dir='/',
        exclude_dirs=['proc', 'mnt', 'dev', 'tmp'],
        root_dir_alias=None,
    ):

        root_dir = str(root_dir)

        accessed_since = self.feature_epoch
        saved_args = locals()
        logger.debug('crawl_files: %s' % (saved_args))
        if self.crawl_mode in [Modes.INVM, Modes.MOUNTPOINT, Modes.OUTCONTAINER]:
            try:
                assert os.path.isdir(root_dir)
                if root_dir_alias is None:
                    root_dir_alias = root_dir
                exclude_dirs = [os.path.join(root_dir, d) for d in
                                exclude_dirs]
                exclude_regex = r'|'.join([fnmatch.translate(d)
                                           for d in exclude_dirs]) or r'$.'

                # walk the directory hierarchy starting at 'root_dir' in BFS
                # order

                feature = self._crawl_file(root_dir, root_dir,
                                           root_dir_alias)
                if feature and (feature.ctime > accessed_since or
                                feature.atime > accessed_since):
                    yield (feature.path, feature)
                for (root_dirpath, dirs, files) in os.walk(root_dir):
                    dirs[:] = [os.path.join(root_dirpath, d) for d in
                               dirs]
                    dirs[:] = [d for d in dirs
                               if not re.match(exclude_regex, d)]
                    files = [os.path.join(root_dirpath, f) for f in
                             files]
                    files = [f for f in files
                             if not re.match(exclude_regex, f)]
                    for fpath in files:
                        feature = self._crawl_file(root_dir, fpath,
                                                   root_dir_alias)
                        if feature and (feature.ctime > accessed_since or
                                        feature.atime > accessed_since):
                            yield (feature.path, feature)
                    for fpath in dirs:
                        feature = self._crawl_file(root_dir, fpath,
                                                   root_dir_alias)
                        if feature and (feature.ctime > accessed_since or
                                        feature.atime > accessed_since):
                            yield (feature.path, feature)
            except Exception as e:
                logger.error('Error crawling root_dir %s' % root_dir,
                             exc_info=True)
                raise CrawlError(e)

    def _filetype(self, fpath, fperm):
        modebit = fperm[0]
        ftype = {
            'l': 'link',
            '-': 'file',
            'b': 'block',
            'd': 'dir',
            'c': 'char',
            'p': 'pipe',
        }.get(modebit)
        return ftype

    _filemode_table = (
        (
            (stat.S_IFLNK, 'l'),
            (stat.S_IFREG, '-'),
            (stat.S_IFBLK, 'b'),
            (stat.S_IFDIR, 'd'),
            (stat.S_IFCHR, 'c'),
            (stat.S_IFIFO, 'p'),
        ),
        ((stat.S_IRUSR, 'r'), ),
        ((stat.S_IWUSR, 'w'), ),
        ((stat.S_IXUSR | stat.S_ISUID, 's'), (stat.S_ISUID, 'S'),
         (stat.S_IXUSR, 'x')),
        ((stat.S_IRGRP, 'r'), ),
        ((stat.S_IWGRP, 'w'), ),
        ((stat.S_IXGRP | stat.S_ISGID, 's'), (stat.S_ISGID, 'S'),
         (stat.S_IXGRP, 'x')),
        ((stat.S_IROTH, 'r'), ),
        ((stat.S_IWOTH, 'w'), ),
        ((stat.S_IXOTH | stat.S_ISVTX, 't'), (stat.S_ISVTX, 'T'),
         (stat.S_IXOTH, 'x')),
    )

    def _fileperm(self, mode):

        # Convert a file's mode to a string of the form '-rwxrwxrwx'

        perm = []
        for table in self._filemode_table:
            for (bit, char) in table:
                if mode & bit == bit:
                    perm.append(char)
                    break
            else:
                perm.append('-')
        return ''.join(perm)

    def _is_executable(self, fpath):
        return os.access(self, fpath, os.X_OK)

    # crawl a single file

    def _crawl_file(
        self,
        root_dir,
        fpath,
        root_dir_alias,
    ):

        try:
            lstat = os.lstat(fpath)
            fmode = lstat.st_mode
            fperm = self._fileperm(fmode)
            ftype = self._filetype(fpath, fperm)
            flinksto = None
            if ftype == 'link':
                try:

                    # This has to be an absolute path, not a root-relative path

                    flinksto = os.readlink(fpath)
                except:
                    logger.error('Error reading linksto info for file %s'
                                 % fpath, exc_info=True)
            fgroup = lstat.st_gid
            fuser = lstat.st_uid

            # root_dir relative path

            frelpath = fpath.replace(root_dir, root_dir_alias, 1)
            (_, fname) = os.path.split(frelpath)
            return FileFeature(
                lstat.st_atime,
                lstat.st_ctime,
                fgroup,
                flinksto,
                fmode,
                lstat.st_mtime,
                fname,
                frelpath,
                lstat.st_size,
                ftype,
                fuser,
            )
        except Exception as e:

            logger.error('Error crawling file %s' % fpath,
                         exc_info=True)
            raise CrawlError(e)

    # default config file discovery heuristic

    @staticmethod
    def _is_config_file(fpath):
        (_, ext) = os.path.splitext(fpath)
        if os.path.isfile(fpath) and ext in [
            '.xml',
            '.ini',
            '.properties',
            '.conf',
            '.cnf',
            '.cfg',
            '.cf',
            '.config',
            '.allow',
            '.deny',
            '.lst',
        ] and os.path.getsize(fpath) <= 204800:
            return True
        return False

    # crawl the given list of configuration files
    def crawl_config_files(
        self,
        root_dir='/',
        exclude_dirs=['proc', 'mnt', 'dev', 'tmp'],
        root_dir_alias=None,
        known_config_files=[],
        discover_config_files=False,
        avoid_setns=False
    ):
        if not (avoid_setns and self.crawl_mode == Modes.OUTCONTAINER):
            for (key, feature) in self._crawl_wrapper(
                    self._crawl_config_files,
                    ['mnt'],
                    root_dir,
                    exclude_dirs,
                    root_dir_alias,
                    known_config_files,
                    discover_config_files):
                yield (key, feature)
        else:
            root_dir = dockerutils.get_docker_container_rootfs_path(
                             self.container.long_id)
            for (key, feature) in self._crawl_config_files(
                    root_dir,
                    exclude_dirs,
                    root_dir_alias,
                    known_config_files,
                    discover_config_files):
                yield (key, feature)


    def _crawl_config_files(
        self,
        root_dir='/',
        exclude_dirs=['proc', 'mnt', 'dev', 'tmp'],
        root_dir_alias=None,
        known_config_files=[],
        discover_config_files=False,
    ):

        saved_args = locals()
        logger.debug('Crawling config files: %s' % (saved_args))
        accessed_since = self.feature_epoch
        try:
            assert os.path.isdir(root_dir)
            if root_dir_alias is None:
                root_dir_alias = root_dir
            exclude_dirs = [os.path.join(root_dir, d) for d in
                            exclude_dirs]
            exclude_regex = r'|'.join([fnmatch.translate(d) for d in
                                       exclude_dirs]) or r'$.'
            known_config_files[:] = [os.path.join(root_dir, f) for f in
                                     known_config_files]
            known_config_files[:] = [f for f in known_config_files
                                     if not re.match(exclude_regex, f)]
            config_file_set = set()
            for fpath in known_config_files:
                if os.path.exists(fpath):
                    lstat = os.lstat(fpath)
                    if (lstat.st_atime > accessed_since or
                            lstat.st_ctime > accessed_since):
                        config_file_set.add(fpath)
        except Exception as e:
            logger.error('Error examining %s' % root_dir, exc_info=True)
            raise CrawlError(e)
        try:
            if discover_config_files:

                # Walk the directory hierarchy starting at 'root_dir' in BFS
                # order looking for config files.

                for (root_dirpath, dirs, files) in os.walk(root_dir):
                    dirs[:] = [os.path.join(root_dirpath, d) for d in
                               dirs]
                    dirs[:] = [d for d in dirs
                               if not re.match(exclude_regex, d)]
                    files = [os.path.join(root_dirpath, f) for f in
                             files]
                    files = [f for f in files
                             if not re.match(exclude_regex, f)]
                    for fpath in files:
                        if os.path.exists(fpath) \
                                and self.is_config_file(fpath):
                            lstat = os.lstat(fpath)
                            if lstat.st_atime > accessed_since \
                                    or lstat.st_ctime > accessed_since:
                                config_file_set.add(fpath)
        except Exception as e:
            logger.error('Error examining %s' % root_dir, exc_info=True)
            raise CrawlError(e)
        try:
            for fpath in config_file_set:
                try:
                    (_, fname) = os.path.split(fpath)
                    frelpath = fpath.replace(root_dir, root_dir_alias,
                                             1)  # root_dir relative path

            # Copy this config_file into / before reading it, so we
            # don't change its atime attribute.

                    (th, temppath) = tempfile.mkstemp(prefix='config.',
                                                      dir='/')
                    os.close(th)
                    shutil.copyfile(fpath, temppath)
                    with codecs.open(filename=fpath, mode='r',
                                     encoding='utf-8', errors='ignore') as \
                            config_file:

                        # Encode the contents of config_file as utf-8.

                        yield (frelpath, ConfigFeature(fname,
                                                       config_file.read(),
                                                       frelpath))
                    os.remove(temppath)
                except IOError as e:
                    raise CrawlError(e)
                except Exception as e:
                    logger.error('Error crawling config file %s'
                                 % fpath, exc_info=True)
                    raise CrawlError(e)
        except Exception as e:
            logger.error('Error examining %s' % root_dir, exc_info=True)
            raise CrawlError(e)

    # crawl disk partition information

    def crawl_disk_partitions(self):
        for (key, feature) in self._crawl_wrapper(
                self._crawl_disk_partitions, ALL_NAMESPACES):
            yield (key, feature)

    def _crawl_disk_partitions(self):

        assert(self.crawl_mode is not Modes.OUTCONTAINER)

        logger.debug('Crawling Disk partitions')
        for partition in psutil.disk_partitions():
            try:
                pdiskusage = psutil.disk_usage(partition.mountpoint)
                yield (partition.mountpoint, DiskFeature(
                    partition.device,
                    100.0 - pdiskusage.percent,
                    partition.fstype,
                    partition.mountpoint,
                    partition.opts,
                    pdiskusage.total,
                ))
            except Exception as e:
                logger.error('Error crawling disk partition %s'
                             % partition.mountpoint, exc_info=True)
                raise CrawlError(e)

    # crawl process metadata

    def crawl_processes(self):
        for (key, feature) in self._crawl_wrapper(
                self._crawl_processes, ALL_NAMESPACES):
            yield (key, feature)

    def _crawl_processes(self):

        created_since = 0
        logger.debug('Crawling Processes: since={0}'.format(created_since))

        list = psutil.process_iter()

        for p in list:
            create_time = (
                p.create_time() if hasattr(
                    p.create_time,
                    '__call__') else p.create_time)
            if create_time > created_since:
                name = (p.name() if hasattr(p.name, '__call__'
                                            ) else p.name)
                cmdline = (p.cmdline() if hasattr(p.cmdline, '__call__'
                                                  ) else p.cmdline)
                pid = (p.pid() if hasattr(p.pid, '__call__') else p.pid)
                status = (p.status() if hasattr(p.status, '__call__'
                                                ) else p.status)
                if status == psutil.STATUS_ZOMBIE:
                    cwd = 'unknown'  # invalid
                else:
                    try:
                        cwd = (p.cwd() if hasattr(p, 'cwd') and
                               hasattr(p.cwd, '__call__') else p.getcwd())
                    except Exception as e:
                        logger.error('Error crawling process %s for cwd'
                                     % pid, exc_info=True)
                        cwd = 'unknown'
                ppid = (p.ppid() if hasattr(p.ppid, '__call__'
                                            ) else p.ppid)
                if (hasattr(p, 'num_threads') and
                        hasattr(p.num_threads, '__call__')):
                    num_threads = p.num_threads()
                else:
                    num_threads = p.get_num_threads()
                try:
                    username = (p.username() if hasattr(p, 'username') and
                                hasattr(p.username, '__call__') else
                                p.username)
                except Exception as e:
                    logger.error('Error crawling process %s for username'
                                 % pid, exc_info=True)
                    username = 'unknown'

                try:
                    openfiles = []
                    for f in p.get_open_files():
                        openfiles.append(f.path)
                    openfiles.sort()
                    feature_key = '{0}/{1}'.format(name, pid)
                    yield (feature_key, ProcessFeature(
                        str(' '.join(cmdline)),
                        create_time,
                        cwd,
                        name,
                        openfiles,
                        pid,
                        ppid,
                        num_threads,
                        username,
                    ))
                except Exception as e:
                    logger.error('Error crawling process %s' % pid,
                                 exc_info=True)
                    raise CrawlError(e)

    # crawl network connection metadata
    def crawl_connections(self):
        for (key, feature) in self._crawl_wrapper(
                self._crawl_connections, ALL_NAMESPACES):
            yield (key, feature)

    def _crawl_connections(self):

        assert(self.crawl_mode is not Modes.OUTCONTAINER)

        created_since = 0
        logger.debug('Crawling Connections: since={0}'.format(created_since))

        list = psutil.process_iter()

        for p in list:
            pid = (p.pid() if hasattr(p.pid, '__call__') else p.pid)
            status = (p.status() if hasattr(p.status, '__call__'
                                            ) else p.status)
            if status == psutil.STATUS_ZOMBIE:
                continue

            create_time = (
                p.create_time() if hasattr(
                    p.create_time,
                    '__call__') else p.create_time)
            name = (p.name() if hasattr(p.name, '__call__') else p.name)

            if create_time <= created_since:
                continue
            try:
                for c in p.get_connections():
                    try:
                        (localipaddr, localport) = c.laddr[:]
                    except:

                        # Older version of psutil uses local_address instead of
                        # laddr.

                        (localipaddr, localport) = c.local_address[:]
                    try:
                        if c.raddr:
                            (remoteipaddr, remoteport) = c.raddr[:]
                        else:
                            (remoteipaddr, remoteport) = (None, None)
                    except:

                        # Older version of psutil uses remote_address instead
                        # of raddr.

                        if c.remote_address:
                            (remoteipaddr, remoteport) = \
                                c.remote_address[:]
                        else:
                            (remoteipaddr, remoteport) = (None, None)
                    feature_key = '{0}/{1}/{2}'.format(pid,
                                                       localipaddr, localport)
                    yield (feature_key, ConnectionFeature(
                        localipaddr,
                        localport,
                        name,
                        pid,
                        remoteipaddr,
                        remoteport,
                        str(c.status),
                    ))
            except Exception as e:
                logger.error('Error crawling connection for process %s'
                             % pid, exc_info=True)
                raise CrawlError(e)

    # crawl performance metric data

    def crawl_metrics(self):
        for (key, feature) in self._crawl_wrapper(
                self._crawl_metrics, ALL_NAMESPACES):
            yield (key, feature)

    def _crawl_metrics(self):

        assert(self.crawl_mode is not Modes.OUTCONTAINER)

        created_since = 0
        logger.debug('Crawling Metrics')
        for p in psutil.process_iter():
            create_time = (
                p.create_time() if hasattr(
                    p.create_time,
                    '__call__') else p.create_time)
            if create_time <= created_since:
                continue
            try:
                name = (p.name() if hasattr(p.name, '__call__'
                                            ) else p.name)
                pid = (p.pid() if hasattr(p.pid, '__call__') else p.pid)
                status = (p.status() if hasattr(p.status, '__call__'
                                                ) else p.status)
                if status == psutil.STATUS_ZOMBIE:
                    continue
                username = (
                    p.username() if hasattr(
                        p.username,
                        '__call__') else p.username)
                meminfo = (
                    p.get_memory_info() if hasattr(
                        p.get_memory_info,
                        '__call__') else p.memory_info)
                ioinfo = (
                    p.get_io_counters() if hasattr(
                        p.get_io_counters,
                        '__call__') else p.io_counters)
                cpu_percent = (
                    p.get_cpu_percent(
                        interval=0) if hasattr(
                        p.get_cpu_percent,
                        '__call__') else p.cpu_percent)
                memory_percent = (
                    p.get_memory_percent() if hasattr(
                        p.get_memory_percent,
                        '__call__') else p.memory_percent)

                feature_key = '{0}/{1}'.format(name, pid)
                yield (feature_key, MetricFeature(
                    round(cpu_percent, 2),
                    round(memory_percent, 2),
                    name,
                    pid,
                    ioinfo.read_bytes,
                    meminfo.rss,
                    str(status),
                    username,
                    meminfo.vms,
                    ioinfo.write_bytes,
                ))
            except Exception as e:
                logger.error('Error crawling metric for process %s'
                             % pid, exc_info=True)
                raise CrawlError(e)

    # crawl Linux package database

    def crawl_packages(self, dbpath=None, root_dir='/', avoid_setns=False):

        if not (avoid_setns and self.crawl_mode == Modes.OUTCONTAINER):
            try:
                for (key, feature) in self._crawl_wrapper(
                        self._crawl_packages, ALL_NAMESPACES, dbpath, root_dir):
                    yield (key, feature)
            except CrawlError as e:
                if self.crawl_mode != Modes.OUTCONTAINER:
                    raise e
                else:
                    avoid_setns

	# If we are here it's because we have to retry avoiding setns(), or we
	# were asked to avoid it
        assert(avoid_setns and self.crawl_mode == Modes.OUTCONTAINER)

        root_dir = dockerutils.get_docker_container_rootfs_path(
                self.container.long_id)
        for (key, feature) in self._crawl_packages(dbpath, root_dir):
            yield (key, feature)


    def _crawl_packages(self, dbpath=None, root_dir='/'):

        # package attributes: ["installed", "name", "size", "version"]

        (installtime, name, version, size) = (None, None, None, None)

        if self.crawl_mode == Modes.INVM:

            logger.debug('Using in-VM state information (crawl mode: ' +
                         self.crawl_mode + ')')
            system_type = platform.system().lower()
            distro = platform.linux_distribution()[0].lower()
            reload_needed = False
        elif self.crawl_mode == Modes.OUTCONTAINER:

            logger.debug('Using outcontainer state information (crawl mode: ' +
                         self.crawl_mode + ')')

            system_type = 'linux'
            distro = ''
            reload_needed = True
        elif self.crawl_mode == Modes.MOUNTPOINT:
            logger.debug('Using disk image information (crawl mode: ' +
                         self.crawl_mode + ')')
            system_type = \
                platform_outofband.system(prefix=root_dir).lower()
            distro = platform_outofband.linux_distribution(prefix=root_dir)[
                0].lower()
            reload_needed = False
        else:
            logger.error('Unsupported crawl mode: ' + self.crawl_mode +
                         '. Skipping package crawl.')
            system_type = 'unknown'
            distro = 'unknown'
            reload_needed = True

        installed_since = self.feature_epoch
        if system_type != 'linux':
            # Package feature is only valid for Linux platforms.

            raise StopIteration()
        logger.debug('Crawling Packages')

        pkg_manager = 'unknown'
        if distro in ['ubuntu', 'debian']:
            pkg_manager = 'dpkg'
        elif distro.startswith('red hat') or distro in ['redhat',
                                                        'fedora', 'centos']:
            pkg_manager = 'rpm'
        elif os.path.exists(os.path.join(root_dir, 'var/lib/dpkg')):
            pkg_manager = 'dpkg'
        elif os.path.exists(os.path.join(root_dir, 'var/lib/rpm')):
            pkg_manager = 'rpm'

        try:
            if pkg_manager == 'dpkg':
                if not dbpath:
                    dbpath = 'var/lib/dpkg'
                for (key, feature) in get_dpkg_packages(
                        root_dir, dbpath, installed_since):
                    yield (key, feature)
            elif pkg_manager == 'rpm':
                if not dbpath:
                    dbpath = 'var/lib/rpm'
                for (key, feature) in get_rpm_packages(
                        root_dir, dbpath, installed_since, reload_needed):
                    yield (key, feature)
            else:
                logger.warning('Unsupported package manager for Linux distro')
        except Exception as e:
            logger.error('Error crawling package %s'
                         % ((name if name else 'Unknown')),
                         exc_info=True)
            raise CrawlError(e)

    # crawl virtual memory information

    def crawl_memory(self):

        # memory attributes: ["used", "buffered", "cached", "free"]

        logger.debug('Crawling memory')
        feature_key = 'memory'

        if self.crawl_mode == Modes.INVM:
            try:
                used = psutil.virtual_memory().used
            except Exception as e:
                used = 'unknown'
            try:
                buffered = psutil.virtual_memory().buffers
            except Exception as e:
                buffered = 'unknown'
            try:
                cached = psutil.virtual_memory().cached
            except Exception as e:
                cached = 'unknown'
            try:
                free = psutil.virtual_memory().free
            except Exception as e:
                free = 'unknown'

            if 'unknown' not in [used, free] and (free + used) > 0:
                util_percentage = float(used) / (free + used) * 100.0
            else:
                util_percentage = 'unknown'

            feature_attributes = MemoryFeature(used, buffered, cached,
                                               free, util_percentage)
        elif self.crawl_mode == Modes.OUTVM:

            (domain_name, kernel_version, distro, arch) = self.vm
            from psvmi import system_info
            sys = system_info(domain_name, kernel_version, distro, arch)
            feature_attributes = MemoryFeature(
                sys.memory_used,
                sys.memory_buffered,
                sys.memory_cached,
                sys.memory_free,
                sys.memory_free / (sys.memory_used + sys.memory_buffered))
        elif self.crawl_mode == Modes.OUTCONTAINER:

            used = buffered = cached = free = 'unknown'
            try:
                with open(self.container.get_memory_cgroup_path('memory.stat'
                                                                ), 'r') as f:
                    for line in f:
                        (key, value) = line.strip().split(' ')
                        if key == 'total_cache':
                            cached = int(value)
                        if key == 'total_active_file':
                            buffered = int(value)

                with open(self.container.get_memory_cgroup_path(
                        'memory.limit_in_bytes'), 'r') as f:
                    limit = int(f.readline().strip())

                with open(self.container.get_memory_cgroup_path(
                        'memory.usage_in_bytes'), 'r') as f:
                    used = int(f.readline().strip())

                host_free = psutil.virtual_memory().free
                container_total = used + min(host_free, limit - used)
                free = container_total - used

                if 'unknown' not in [used, free] and (free + used) > 0:
                    util_percentage = float(used) / (free + used) * 100.0
                else:
                    util_percentage = 'unknown'

                feature_attributes = MemoryFeature(
                    used, buffered, cached, free, util_percentage)
            except Exception as e:

                logger.error('Error crawling memory', exc_info=True)
                raise CrawlError(e)
        else:

            logger.error('Unsupported crawl mode: ' + self.crawl_mode +
                         '. Returning unknown memory key and attributes.'
                         )
            feature_attributes = MemoryFeature('unknown', 'unknown',
                                               'unknown', 'unknown')
        try:
            yield (feature_key, feature_attributes)
        except Exception as e:
            logger.error('Error crawling memory', exc_info=True)
            raise CrawlError(e)

    def _save_container_cpu_times(self, container_long_id, times):
        cache_key = container_long_id
        self._cache_put_value(cache_key, times)

    def _get_prev_container_cpu_times(self, container_long_id):
        cache_key = container_long_id
        return self._cache_get_value(cache_key)

    def crawl_cpu(self, per_cpu=False):

        logger.debug('Crawling cpu information')

        if self.crawl_mode not in [
                Modes.INVM,
                Modes.OUTCONTAINER,
                Modes.OUTVM]:
            logger.error('Unsupported crawl mode: ' + self.crawl_mode +
                         '. Returning unknown memory key and attributes.'
                         )
            feature_attributes = CpuFeature(
                'unknown',
                'unknown',
                'unknown',
                'unknown',
                'unknown',
                'unknown',
                'unknown',
                'unknown',
            )

        host_cpu_feature = {}
        if self.crawl_mode in [Modes.INVM, Modes.OUTCONTAINER]:
            for (index, cpu) in \
                    enumerate(psutil.cpu_times_percent(percpu=True)):

                try:
                    idle = cpu.idle
                except Exception as e:
                    idle = 'unknown'
                try:
                    nice = cpu.nice
                except Exception as e:
                    nice = 'unknown'
                try:
                    user = cpu.user
                except Exception as e:
                    user = 'unknown'
                try:
                    wait = cpu.iowait
                except Exception as e:
                    wait = 'unknown'
                try:
                    system = cpu.system
                except Exception as e:
                    system = 'unknown'
                try:
                    interrupt = cpu.irq
                except Exception as e:
                    interrupt = 'unknown'
                try:
                    steal = cpu.steal
                except Exception as e:
                    steal = 'unknown'

                used = 100 - int(idle)

                feature_key = '{0}-{1}'.format('cpu', index)
                feature_attributes = CpuFeature(
                    idle,
                    nice,
                    user,
                    wait,
                    system,
                    interrupt,
                    steal,
                    used,
                )
                host_cpu_feature[index] = feature_attributes
                if self.crawl_mode == Modes.INVM:
                    try:
                        yield (feature_key, feature_attributes)
                    except Exception as e:
                        logger.error('Error crawling cpu information',
                                     exc_info=True)
                        raise CrawlError(e)

        if self.crawl_mode == Modes.OUTCONTAINER:

            if per_cpu:
                stat_file_name = 'cpuacct.usage_percpu'
            else:
                stat_file_name = 'cpuacct.usage'

            container = self.container

            try:
                (cpu_usage_t1, prev_time) = \
                    self._get_prev_container_cpu_times(container.long_id)

                if cpu_usage_t1:
                    logger.debug('Using previous cpu times for container %s'
                                 % container.long_id)
                    interval = time.time() - prev_time

                if not cpu_usage_t1 or interval == 0:
                    logger.debug(
                        'There are no previous cpu times for container %s '
                        'so we will be sleeping for 100 milliseconds' %
                        container.long_id)

                    with open(container.get_cpu_cgroup_path(stat_file_name),
                              'r') as f:
                        cpu_usage_t1 = f.readline().strip().split(' ')
                    interval = 0.1  # sleep for 100ms
                    time.sleep(interval)

                with open(container.get_cpu_cgroup_path(stat_file_name),
                          'r') as f:
                    cpu_usage_t2 = f.readline().strip().split(' ')

                # Store the cpu times for the next crawl

                self._save_container_cpu_times(container.long_id,
                                               cpu_usage_t2)
            except Exception as e:
                logger.error('Error crawling cpu information',
                             exc_info=True)
                raise CrawlError(e)

            cpu_user_system = {}
            try:
                path = container.get_cpu_cgroup_path('cpuacct.stat')
                with open(path, 'r') as f:
                    for line in f:
                        m = re.search(r"(system|user)\s+(\d+)", line)
                        if m:
                            cpu_user_system[m.group(1)] = \
                                float(m.group(2))
            except Exception as e:
                logger.error('Error crawling cpu information',
                             exc_info=True)
                raise CrawlError(e)

            for (index, cpu_usage_ns) in enumerate(cpu_usage_t1):
                usage_secs = (float(cpu_usage_t2[index]) -
                              float(cpu_usage_ns)) / float(1e9)

                # Interval is never 0 because of step 0 (forcing a sleep)

                usage_percent = usage_secs / interval * 100.0
                if usage_percent > 100.0:
                    usage_percent = 100.0
                idle = 100.0 - usage_percent

                # Approximation 1

                user_plus_sys_hz = cpu_user_system['user'] \
                    + cpu_user_system['system']
                if user_plus_sys_hz == 0:
                    # Fake value to avoid divide by zero.
                    user_plus_sys_hz = 0.1
                user = usage_percent * (cpu_user_system['user'] /
                                        user_plus_sys_hz)
                system = usage_percent * (cpu_user_system['system'] /
                                          user_plus_sys_hz)

                # Approximation 2

                nice = host_cpu_feature[index][1]
                wait = host_cpu_feature[index][3]
                interrupt = host_cpu_feature[index][5]
                steal = host_cpu_feature[index][6]
                feature_key = '{0}-{1}'.format('cpu', index)
                feature_attributes = CpuFeature(
                    idle,
                    nice,
                    user,
                    wait,
                    system,
                    interrupt,
                    steal,
                    usage_percent,
                )
                try:
                    yield (feature_key, feature_attributes)
                except Exception as e:
                    logger.error('Error crawling cpu information',
                                 exc_info=True)
                    raise CrawlError(e)

    def crawl_interface(self):
        for (ifname, curr_count) in self._crawl_wrapper(
                self._crawl_interface_counters,
                ['net']):
            feature_key = '{0}-{1}'.format('interface', ifname)
            cache_key = '{0}-{1}'.format(self.namespace, feature_key)

            (prev_count, prev_time) = self._cache_get_value(cache_key)
            self._cache_put_value(cache_key, curr_count)

            if prev_count and prev_time:
                d = time.time() - prev_time
                diff = [(a - b) / d for (a, b) in zip(curr_count,
                                                      prev_count)]
            else:

                # first measurement

                diff = [
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                ]

            feature_attributes = InterfaceFeature._make(diff)

            yield (feature_key, feature_attributes)

    def _crawl_interface_counters(self):

        logger.debug('Crawling interface information')

        for ifname in psutil.net_io_counters(pernic=True):
            try:
                interface = psutil.net_io_counters(pernic=True)[ifname]
            except:
                continue

            try:
                bytes_sent = interface.bytes_sent
            except Exception as e:
                bytes_sent = 'unknown'
            try:
                bytes_recv = interface.bytes_recv
            except Exception as e:
                bytes_recv = 'unknown'

            try:
                packets_sent = interface.packets_sent
            except Exception as e:
                packets_sent = 'unknown'
            try:
                packets_recv = interface.packets_recv
            except Exception as e:
                packets_recv = 'unknown'

            try:
                errout = interface.errout
            except Exception as e:
                errout = 'unknown'
            try:
                errin = interface.errin
            except Exception as e:
                errin = 'unknown'

            curr_count = [
                bytes_sent,
                bytes_recv,
                packets_sent,
                packets_recv,
                errout,
                errin,
            ]

            try:
                yield (ifname, curr_count)
            except Exception as e:
                logger.error('Error crawling interface information',
                             exc_info=True)
                raise CrawlError(e)

    def crawl_load(self):
        for (key, feature) in self._crawl_wrapper(
                self._crawl_load, ALL_NAMESPACES):
            yield (key, feature)

    def _crawl_load(self):

        assert(self.crawl_mode is not Modes.OUTCONTAINER)

        logger.debug('Crawling system load')
        feature_key = 'load'

        try:
            shortterm = os.getloadavg()[0]
        except Exception as e:
            shortterm = 'unknown'
        try:
            midterm = os.getloadavg()[1]
        except Exception as e:
            midterm = 'unknown'
        try:
            longterm = os.getloadavg()[2]
        except Exception as e:
            longterm = 'unknown'

        feature_attributes = LoadFeature(shortterm, midterm, longterm)

        try:
            yield (feature_key, feature_attributes)
        except Exception as e:
            logger.error('Error crawling load', exc_info=True)
            raise CrawlError(e)

    def crawl_dockerps(self):
        assert(self.crawl_mode == Modes.INVM)
        logger.debug('Crawling docker ps results')

        try:
            for inspect in dockerutils.exec_dockerps():
                long_id = inspect['Id']
                state = inspect['State']
                running = state['Running']
                image = inspect['Image']
                names = inspect['Name']
                cmd = inspect['Config']['Cmd']
                yield (long_id, DockerPSFeature._make([
                    running,
                    0,
                    image,
                    [],
                    cmd,
                    names,
                    long_id,
                ]))
        except Exception as e:
            logger.error('Error crawling docker ps', exc_info=True)
            raise CrawlError(e)

    def crawl_dockerhistory(self):
        logger.debug('Crawling docker history')

        long_id = self.container.long_id
        try:
            history = dockerutils.exec_docker_history(long_id)
            image_id = history[0]['Id']
            yield (image_id, {'history': history})
        except Exception as e:
            logger.error('Error crawling docker history', exc_info=True)
            raise CrawlError(e)

    def crawl_dockerinspect(self):
        logger.debug('Crawling docker inspect')

        long_id = self.container.long_id
        try:
            inspect = dockerutils.exec_dockerinspect(long_id)
            yield (long_id, inspect)
        except Exception as e:
            logger.error('Error crawling docker inspect', exc_info=True)
            raise CrawlError(e)

    def _crawl_wrapper(self, _function, namespaces=ALL_NAMESPACES, *args):
        # TODO: add kwargs
        if self.crawl_mode == Modes.OUTCONTAINER:
            features = self._crawl_as_container(_function, namespaces, *args)
        else:
            features = _function(*args)

        for (key, feature) in features:
            yield (key, feature)

    def _crawl_as_container(self, _function, namespaces=ALL_NAMESPACES, *args):
        assert(self.crawl_mode == Modes.OUTCONTAINER)

        self.crawl_mode = Modes.INVM
        try:
            for (key, feature) in \
                run_as_another_namespace(self.container.pid,
                                         namespaces, _function, *args):
                if feature is not None:
                    yield (key, feature)
        finally:
            self.crawl_mode = Modes.OUTCONTAINER

    def _crawl_test_infinite_loop(self):
        while True:
            a = 1
        print a

    def crawl_test_infinite_loop(self):
        for (key, feature) in self._crawl_wrapper(
                self._crawl_test_infinite_loop, ALL_NAMESPACES):
            yield (key, feature)

    def _crawl_test_crash(self):
        raise CrawlError("oops")

    def crawl_test_crash(self):
        for (key, feature) in self._crawl_wrapper(
                self._crawl_test_crash, ALL_NAMESPACES):
            yield (key, feature)
