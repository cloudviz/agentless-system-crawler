#!/usr/bin/python

#
# (c) Copyright IBM Corp.2014,2015
#
# Collection of crawlers that extract specific types of features from
# the host machine. This code is portable across OS platforms (Linux, Windows)
#

import sys
import platform
import os
import stat
import logging
from collections import namedtuple,OrderedDict
import socket
import codecs
import subprocess
import tempfile
import gzip
import shutil
import fnmatch
import re
import time
import csv
import commands
from datetime import datetime
import copy
#from mtgraphite import MTGraphiteClient
import cPickle as pickle
import multiprocessing
import errno
#from timeout import timeout

# Additional modules
import platform_outofband

# External dependencies that must be easy_install'ed separately
import simplejson as json
import psutil
import requests
from netifaces import interfaces, ifaddresses, AF_INET

logger = logging.getLogger("crawlutils")

OSFeature = namedtuple('OSFeature', ["boottime", "ipaddr", "osdistro", "osname", "osplatform", "osrelease", "ostype", "osversion"])
FileFeature = namedtuple('FileFeature', ["atime", "ctime", "gid", "linksto", "mode", "mtime", "name", "path", "size", "type", "uid"])
ConfigFeature = namedtuple('ConfigFeature', ["name", "content", "path"])
DiskFeature = namedtuple('DiskFeature', ["partitionname", "freepct", "fstype", "mountpt", "mountopts", "partitionsize"])
ProcessFeature = namedtuple('ProcessFeature', ["cmd", "created", "cwd", "pname", "openfiles", "pid", "ppid", "threads", "user"])
MetricFeature = namedtuple('MetricFeature', ["cpupct", "mempct", "pname", "pid", "read", "rss", "status", "user", "vms", "write"])
ConnectionFeature = namedtuple('ConnectionFeature', ["localipaddr", "localport", "pname", "pid", "remoteipaddr", "remoteport", "connstatus"])
PackageFeature = namedtuple('PackageFeature', ["installed", "pkgname", "pkgsize", "pkgversion"])
MemoryFeature = namedtuple('MemoryFeature', ["memory_used", "memory_buffered", "memory_cached", "memory_free"])
CpuFeature = namedtuple('CpuFeature', ["cpu_idle", "cpu_nice", "cpu_user", "cpu_wait", "cpu_system", "cpu_interrupt", "cpu_steal"])
InterfaceFeature = namedtuple('InterfaceFeature', ["if_octets_tx", "if_octets_rx", "if_packets_tx", "if_packets_rx", "if_errors_tx", "if_errors_rx"])
LoadFeature = namedtuple('LoadFeature', ["shortterm", "midterm", "longterm"])
DockerPSFeature = namedtuple('DockerPSFeature', ["Status", "Created", "Image", "Ports", "Command", "Names", "Id" ])
DockerHistoryFeature = namedtuple('DockerHistoryFeature', ["history" ])

Container = namedtuple('Container', ['pid', 'short_id', 'long_id', 'name', 'image', 'namespace'])

FEATURE_SCHEMA = {
    'os' : OSFeature._fields,
    'file' : FileFeature._fields,
    'config' : ConfigFeature._fields,
    'disk' : DiskFeature._fields,
    'process' : ProcessFeature._fields,
    'connection' : ConnectionFeature._fields,
    'metric' : MetricFeature._fields,
    'package' : PackageFeature._fields,
    'memory' : MemoryFeature._fields,
    'cpu' : CpuFeature._fields,
    'interface' : InterfaceFeature._fields,
    'load' : LoadFeature._fields,
    'dockerps' : DockerPSFeature._fields,
    'dockerhistory' : DockerHistoryFeature._fields
}


class CrawlException(Exception):

    def __init__(self, e):
        pass


# try to determine this host's IP address
def get_host_ipaddr():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('www.ibm.com', 9))
        return s.getsockname()[0]
    except socket.error:
        return None
    finally:
        del s
    
def get_host_ip4_addresses():
    ip_list = []
    for interface in interfaces():
        if AF_INET in ifaddresses(interface):
            for link in ifaddresses(interface)[AF_INET]:
                ip_list.append(link['addr'])
    return ip_list


class Crawler:
    
    @staticmethod
    def get_feature_schema():
        return FEATURE_SCHEMA
    
    # feature_epoch must be a UTC timestamp. If > 0 only features accessed/modified/created since this time are crawled
    def __init__(self, feature_epoch=0, ignore_exceptions=True,
                 config_file_discovery_heuristic=None, crawl_mode='INVM',
                 vm=None, container_long_id=None, namespace=None):
        logger.info('Initilizing crawler: feature_epoch={0}, ignore_exceptions={1}, config_file_discovery_heuristic={2}'.format(
                    feature_epoch, ignore_exceptions, config_file_discovery_heuristic))
        self.feature_epoch = feature_epoch
        self.ignore_exceptions = ignore_exceptions
        self.is_config_file = config_file_discovery_heuristic or Crawler._is_config_file
        #TODO: Define crawl mode as custom type!! #'INVM', 'MOUNTPOINT', 'DEVICE', 'FILE', etc. 
        self.crawl_mode = crawl_mode

        # Used for OUTCONTAINER crawl mode
        self.container_long_id = container_long_id
        # Used by crawl_interface
        self.namespace = namespace
        # Used for OUTVM crawl mode
        self.vm = vm # tuple like ('instance-00000172', 'x86_64', '3.3.3')
    
    #crawl the OS information
    # mountpoint only used for out-of-band crawling
    def crawl_os(self, mountpoint=None):
        # os attributes: ["boottime", "osdistro", "ipaddr", "osname", "osplatform", "osrelease", "ostype", "osversion"]
        # os    "linux" -->  platform.system().lower()
        #               {"boottime":1394049039.0, --> psutil.boot_time()
        #                "ipaddr":"10.154.163.164", --> get_host_ipaddr()
        #                "osdistro":"Ubuntu", --> platform_outofband.linux_distribution(prefix=mountpoint)[0],
        #                "osname":"Linux-3.11.0-12-generic-i686-with-Ubuntu-13.10-saucy", --> platform_outofband.platform(),
        #                "osplatform":"i686", --> platform_outofband.machine(prefix=mountpoint),
        #                "osrelease":"3.11.0-12-generic", --> platform_outofband.release(prefix=mountpoint),
        #                "ostype":"linux", --> platform_outofband.system(prefix=mountpoint).lower(),
        #                "osversion":"#19-Ubuntu SMP Wed Oct 9 16:12:00 UTC 2013"} --> platform_outofband.version(prefix=mountpoint)
        
        logger.debug('Crawling OS')
        if self.crawl_mode == 'INVM': 
            logger.debug('Using in-VM state information (crawl mode: ' + self.crawl_mode + ')')
            feature_key = platform.system().lower()

            try: ips = get_host_ip4_addresses()
            except Exception, e: ips = 'unknown'
            try: distro = platform.linux_distribution()[0]
            except Exception, e: distro = 'unknown'
            try: osname = platform.platform()
            except Exception, e: osname = 'unknown'

            boot_time = (psutil.boot_time() if hasattr(psutil, "boot_time")
                         else psutil.BOOT_TIME)
            feature_attributes = OSFeature(boot_time, ips, distro, osname,
                                           platform.machine(), platform.release(),
                                           platform.system().lower(), platform.version())
        elif self.crawl_mode == 'MOUNTPOINT': 
            logger.debug('Using disk image information (crawl mode: ' + self.crawl_mode + ')')
            if (mountpoint is None) or (not os.path.exists(mountpoint)):
                logger.error('Mountpoint: ' + mountpoint + ' does not exist.')
                feature_key = 'unknown'
                feature_attributes = OSFeature('unknown', 'unknown', 'unknown', 'unknown', 
                                               'unknown', 'unknown', 'unknown', 'unknown')
            else:
                feature_key = platform_outofband.system(prefix=mountpoint).lower()
                feature_attributes = OSFeature("unsupported", # boot time unknown for img
                                               "0.0.0.0", # live IP unknown for img
                                               platform_outofband.linux_distribution(prefix=mountpoint)[0], 
                                               platform_outofband.platform(prefix=mountpoint), 
                                               platform_outofband.machine(prefix=mountpoint), 
                                               platform_outofband.release(prefix=mountpoint), 
                                               platform_outofband.system(prefix=mountpoint).lower(), 
                                               platform_outofband.version(prefix=mountpoint)
                                               )
        elif self.crawl_mode == 'OUTVM':
            domain_name, kernel_version, distro, arch = self.vm
            from psvmi import system_info
            sys = system_info(domain_name, kernel_version, distro, arch)
            feature_attributes = OSFeature(sys.boottime, sys.ipaddr,
                sys.osdistro, sys.osname,sys.osplatform,sys.osrelease,
                sys.ostype,sys.osversion)
            feature_key = sys.ostype
        else:
            logger.error('Unsupported crawl mode: ' + self.crawl_mode + '. Returning unknown OS key and attributes.')
            feature_key = 'unknown'
            feature_attributes = OSFeature('unknown', 'unknown', 'unknown', 'unknown', 
                                           'unknown', 'unknown', 'unknown', 'unknown')
        try:
            yield feature_key, feature_attributes
        except Exception, e:
            logger.error('Error crawling OS', exc_info=True)
            if not self.ignore_exceptions:
                raise CrawlException(e)
    
    # crawl the directory hierarchy under root_dir
    def crawl_files(self, root_dir='/', exclude_dirs=['proc','mnt','dev','tmp'], root_dir_alias=None):
        accessed_since = self.feature_epoch
        logger.debug('Crawling Files: root_dir={0}, exclude_dirs={1}, root_dir_alias={2}, accessed_since={3}'.format(
                                                                            root_dir, exclude_dirs, root_dir_alias, accessed_since))
        try:
            assert os.path.isdir(root_dir)
            if root_dir_alias is None:
                root_dir_alias = root_dir
            exclude_dirs = [os.path.join(root_dir, d) for d in exclude_dirs]
            exclude_regex = r'|'.join([fnmatch.translate(d) for d in exclude_dirs]) or r'$.'
            # walk the directory hierarchy starting at 'root_dir' in BFS order
            feature = self._crawl_file(root_dir, root_dir, root_dir_alias)
            if feature and (feature.ctime > accessed_since or feature.atime > accessed_since):
                yield feature.path, feature
            for root_dirpath, dirs, files in os.walk(root_dir):
                dirs[:] = [os.path.join(root_dirpath, d) for d in dirs]
                dirs[:] = [d for d in dirs if not re.match(exclude_regex, d)]
                files = [os.path.join(root_dirpath, f) for f in files]
                files = [f for f in files if not re.match(exclude_regex, f)]
                for fpath in files:
                    feature = self._crawl_file(root_dir, fpath, root_dir_alias)
                    if feature and (feature.ctime > accessed_since or feature.atime > accessed_since):
                        yield feature.path, feature
                for fpath in dirs:
                    feature = self._crawl_file(root_dir, fpath, root_dir_alias)
                    if feature and (feature.ctime > accessed_since or feature.atime > accessed_since):
                        yield feature.path, feature
        except Exception, e:
            logger.error('Error crawling root_dir %s' % root_dir, exc_info=True)
            if not self.ignore_exceptions:
                raise CrawlException(e)

    def _filetype(self, fpath, fperm):
        modebit = fperm[0]
        ftype = {
                 'l': 'link',
                 '-': 'file',
                 'b': 'block',
                 'd': 'dir',
                 'c': 'char',
                 'p': 'pipe'
        }.get(modebit)
        return ftype
    
    _filemode_table = (
        ((stat.S_IFLNK, "l"), (stat.S_IFREG, "-"), (stat.S_IFBLK, "b"), (stat.S_IFDIR, "d"), (stat.S_IFCHR, "c"), (stat.S_IFIFO, "p")),
        ((stat.S_IRUSR, "r"),),
        ((stat.S_IWUSR, "w"),),
        ((stat.S_IXUSR|stat.S_ISUID, "s"), (stat.S_ISUID, "S"), (stat.S_IXUSR, "x")),
        ((stat.S_IRGRP,  "r"),),
        ((stat.S_IWGRP,  "w"),),
        ((stat.S_IXGRP|stat.S_ISGID, "s"), (stat.S_ISGID, "S"), (stat.S_IXGRP, "x"),),
        ((stat.S_IROTH, "r"),),
        ((stat.S_IWOTH, "w"),),
        ((stat.S_IXOTH|stat.S_ISVTX, "t"), (stat.S_ISVTX, "T"), (stat.S_IXOTH, "x"))
    )
    
    def _fileperm(self, mode):
        # Convert a file's mode to a string of the form '-rwxrwxrwx'
        perm = []
        for table in self._filemode_table:
            for bit, char in table:
                if mode & bit == bit:
                    perm.append(char)
                    break
            else:
                perm.append("-")
        return "".join(perm)
    
    def _is_executable(self, fpath):
        return os.access(self, fpath, os.X_OK)
    
    # crawl a single file
    def _crawl_file(self, root_dir, fpath, root_dir_alias):
        # file attributes: ["atime", "ctime", "group", "linksto", "mode", "mtime", "name", "path", "size", "type", "user"]
        try:
            lstat = os.lstat(fpath)
            fmode = lstat.st_mode
            fperm = self._fileperm(fmode)
            ftype = self._filetype(fpath, fperm)
            flinksto = None
            if ftype == 'link':
                try:
                    flinksto = os.readlink(fpath) # this has to be an absolute path, not a root-relative path
                except:
                    logger.error('Error reading linksto info for file %s' % fpath, exc_info=True)
            fgroup = lstat.st_gid
            fuser = lstat.st_uid
            frelpath = fpath.replace(root_dir, root_dir_alias, 1) # root_dir relative path
            _, fname = os.path.split(frelpath)
            return FileFeature(lstat.st_atime, lstat.st_ctime, fgroup, flinksto,
                               fmode, lstat.st_mtime, fname, frelpath, lstat.st_size, ftype, fuser)
            #Doing below temporarily to get rid of atime pollution
#             return FileFeature(0, lstat.st_ctime, fgroup, flinksto,
#                                fmode, lstat.st_mtime, fname, frelpath, lstat.st_size, ftype, fuser)
        except Exception, e:
            logger.error('Error crawling file %s' % fpath, exc_info=True)
            if not self.ignore_exceptions:
                raise CrawlException(e)
    
    # default config file discovery heuristic
    @staticmethod
    def _is_config_file(fpath):
        _, ext = os.path.splitext(fpath)
        if os.path.isfile(fpath) and ext in ['.xml', '.ini', '.properties', '.conf', '.cnf', '.cfg', '.cf', '.config', '.allow', '.deny', '.lst'] and os.path.getsize(fpath) <= 204800:
            return True
        return False
    
    # crawl the given list of configuration files
    def crawl_config_files(self, root_dir='/', exclude_dirs=['proc','mnt','dev','tmp'], root_dir_alias=None, known_config_files=[], discover_config_files=False):
        # config attributes: ["name", "content", "path"]
        accessed_since = self.feature_epoch
        logger.debug('Crawling Config files: root_dir={0}, exclude_dirs={1}, root_dir_alias={2}, accessd_since={3}, known_config_files={4}, discover_config_files={5}'.format(
                                            root_dir, exclude_dirs, root_dir_alias, accessed_since, known_config_files, discover_config_files))
        try:
            assert os.path.isdir(root_dir)
            if root_dir_alias is None:
                root_dir_alias = root_dir
            exclude_dirs = [os.path.join(root_dir, d) for d in exclude_dirs]
            exclude_regex = r'|'.join([fnmatch.translate(d) for d in exclude_dirs]) or r'$.'
            known_config_files[:] = [os.path.join(root_dir, f) for f in known_config_files]
            known_config_files[:] = [f for f in known_config_files if not re.match(exclude_regex, f)]
            config_file_set = set()
            for fpath in known_config_files:
                if os.path.exists(fpath):
                    lstat = os.lstat(fpath)
                    if lstat.st_atime > accessed_since or lstat.st_ctime > accessed_since:
                        config_file_set.add(fpath)
        except Exception, e:
            logger.error('Error examining %s' % root_dir, exc_info=True)
            if not self.ignore_exceptions:
                raise CrawlException(e)
        try:
            if discover_config_files:
                # walk the directory hierarchy starting at 'root_dir' in BFS order looking for config files
                for root_dirpath, dirs, files in os.walk(root_dir):
                    dirs[:] = [os.path.join(root_dirpath, d) for d in dirs]
                    dirs[:] = [d for d in dirs if not re.match(exclude_regex, d)]
                    files = [os.path.join(root_dirpath, f) for f in files]
                    files = [f for f in files if not re.match(exclude_regex, f)]
                    for fpath in files:
                        if os.path.exists(fpath) and self.is_config_file(fpath):
                            lstat = os.lstat(fpath)
                            if lstat.st_atime > accessed_since or lstat.st_ctime > accessed_since:
                                config_file_set.add(fpath)
        except Exception, e:
            logger.error('Error examining %s' % root_dir, exc_info=True)
            if not self.ignore_exceptions:
                raise CrawlException(e)
        try:
            for fpath in config_file_set:
                try:
                    _, fname = os.path.split(fpath)
                    frelpath = fpath.replace(root_dir, root_dir_alias, 1) # root_dir relative path
                    # copy this config_file into / before reading it, so we don't change its atime attribute
                    (th, temppath) = tempfile.mkstemp(prefix='config.', dir='/')
                    os.close(th)
                    shutil.copyfile(fpath, temppath)                 
                    with codecs.open(filename=fpath, mode='r', encoding='utf-8', errors='ignore') as config_file: # encode the contents of config_file as utf-8
                        yield frelpath, ConfigFeature(fname, config_file.read(), frelpath)
                    os.remove(temppath)
                except IOError, e:
                    print "Unable to copy file. %s" % e
                    if not self.ignore_exceptions:
                        raise CrawlException(e)
                except Exception, e:
                    print fpath, temppath, frelpath
                    logger.error('Error crawling config file %s' % fpath, exc_info=True)
                    if not self.ignore_exceptions:
                        raise CrawlException(e)
        except Exception, e:
            logger.error('Error examining %s' % root_dir, exc_info=True)
            if not self.ignore_exceptions:
                raise CrawlException(e)
    
    
    # crawl disk partition information
    def crawl_disk_partitions(self):
        # disk attributes: ["device", "freepct", "fstype", "mountpt", "options", "size"]
        logger.debug('Crawling Disk partitions')
        for partition in psutil.disk_partitions():
            try:
                pdiskusage = psutil.disk_usage(partition.mountpoint)
                yield partition.mountpoint, DiskFeature(partition.device, (100.0 - pdiskusage.percent), partition.fstype, 
                                                     partition.mountpoint, partition.opts, pdiskusage.total)
            except Exception, e:
                logger.error("Error crawling disk partition %s" % partition.mountpoint, exc_info=True)
                if not self.ignore_exceptions:
                    raise CrawlException(e)
    
    # crawl process metadata
    def crawl_processes(self):
        # process attributes: ["cmd", "created", "cwd", "pname", "openfiles", "pid", "ppid", "threads", "user"]
        # Always do a full crawl since epoch:
        #created_since = self.feature_epoch
        created_since = 0
        logger.debug('Crawling Processes: created_since={0}'.format(created_since))

        if self.crawl_mode == 'INVM': 
            list = psutil.process_iter()
        elif self.crawl_mode == 'OUTVM':
            domain_name, kernel_version, distro, arch = self.vm
            from psvmi import process_iter
            list = process_iter(domain_name, kernel_version, distro, arch)

        for p in list:
            create_time = p.create_time() if hasattr(p.create_time, '__call__') \
                                          else p.create_time
            if create_time > created_since:
                name = p.name() if hasattr(p.name, '__call__') else p.name
                cmdline = p.cmdline() if hasattr(p.cmdline, '__call__') else p.cmdline
                pid = p.pid() if hasattr(p.pid, '__call__') else p.pid
                status = p.status() if hasattr(p.status, '__call__') else p.status
                if status == psutil.STATUS_ZOMBIE:
                    cwd = "unknown" # invalid
                else:
                    try:
                        cwd = p.cwd() if hasattr(p, "cwd") and hasattr(p.cwd, '__call__') else p.getcwd()
                    except Exception, e:
                        logger.error('Error crawling process %s for cwd' % pid, exc_info=True)
                        cwd = 'unknown'
                ppid = p.ppid() if hasattr(p.ppid, '__call__') else p.ppid
                num_threads = p.num_threads() if hasattr(p, "num_threads") and hasattr(p.num_threads, '__call__') \
                                              else p.get_num_threads()
                try:
                    username = p.username() if hasattr(p, "username") and hasattr(p.username, '__call__') else p.username
                except Exception, e:
                    logger.error('Error crawling process %s for username' % pid, exc_info=True)
                    username = 'unknown'

                try:
                    openfiles = []
                    for f in p.get_open_files():
                        openfiles.append(f.path)
                    openfiles.sort()
                    default_key = '{0}/{1}'.format(name, pid)
                    yield default_key, ProcessFeature(str(' '.join(cmdline)), create_time, cwd, name,
                                                      openfiles, pid, ppid, num_threads, username)
                except Exception, e:
                    logger.error('Error crawling process %s' % pid, exc_info=True)
                    if not self.ignore_exceptions:
                        raise CrawlException(e)
    
    # crawl network connection metadata
    def crawl_connections(self):
        # connection attributes: ["localipaddr", "localport", "pname", "pid", "remoteipaddr", "remoteport", "status"]
        # Always do a full crawl since epoch:
        #created_since = self.feature_epoch
        created_since = 0
        logger.debug('Crawling Connections: created_since={0}'.format(created_since))

        if self.crawl_mode == 'INVM': 
            list = psutil.process_iter()
        elif self.crawl_mode == 'OUTVM':
            domain_name, kernel_version, distro, arch = self.vm
            from psvmi import process_iter
            list = process_iter(domain_name, kernel_version, distro, arch)

        for p in list:
            pid = p.pid() if hasattr(p.pid, '__call__') else p.pid
            status = p.status() if hasattr(p.status, '__call__') else p.status
            if status == psutil.STATUS_ZOMBIE: continue

            create_time = p.create_time() if hasattr(p.create_time, '__call__') \
                                          else p.create_time
            name = p.name() if hasattr(p.name, '__call__') else p.name

            if create_time <= created_since:
                continue
            try:
                for c in p.get_connections():
                    try:
                        localipaddr, localport = c.laddr[:]
                    except: # older version of psutil uses local_address instead of laddr
                        localipaddr, localport = c.local_address[:]
                    try:
                        if c.raddr:
                            remoteipaddr, remoteport = c.raddr[:]
                        else:
                            remoteipaddr, remoteport = None, None
                    except: # older version of psutil uses remote_address instead of raddr
                        if c.remote_address:
                            remoteipaddr, remoteport = c.remote_address[:]
                        else:
                            remoteipaddr, remoteport = None, None                    
                    default_key = '{0}/{1}/{2}'.format(pid, localipaddr, localport)
                    yield default_key, ConnectionFeature(localipaddr, localport, name, pid, remoteipaddr, remoteport, str(c.status))
            except Exception, e:
                logger.error('Error crawling connection for process %s' % pid, exc_info=True)
                if not self.ignore_exceptions:
                    raise CrawlException(e)
    
    # crawl performance metric data
    def crawl_metrics(self):
        # metric attributes: ["cpupct", "mempct", "name", "pid", "read", "rss", "status", "user", "vms", "write"] 
        # Always do a full crawl since epoch:
        #created_since = self.feature_epoch
        created_since = 0
        logger.debug('Crawling Metrics')
        for p in psutil.process_iter():
            create_time = p.create_time() if hasattr(p.create_time, '__call__') else p.create_time
            if create_time <= created_since:
                continue
            try:
                name = p.name() if hasattr(p.name, '__call__') else p.name
                pid = p.pid() if hasattr(p.pid, '__call__') else p.pid
                status = p.status() if hasattr(p.status, '__call__') else p.status
                if status == psutil.STATUS_ZOMBIE:
                    continue
                username = p.username() if hasattr(p.username, '__call__') else p.username
                meminfo = p.get_memory_info() if hasattr(p.get_memory_info, '__call__') else p.memory_info
                ioinfo = p.get_io_counters() if hasattr(p.get_io_counters, '__call__') else p.io_counters
                cpu_percent = p.get_cpu_percent(interval=0) if hasattr(p.get_cpu_percent, '__call__') else p.cpu_percent
                memory_percent = p.get_memory_percent() if hasattr(p.get_memory_percent, '__call__') else p.memory_percent

                default_key = '{0}/{1}'.format(name, pid)
                yield default_key, \
                      MetricFeature(round(cpu_percent, 2),
                                    round(memory_percent, 2),
                                    name, pid, ioinfo.read_bytes,
                                    meminfo.rss, str(status),
                                    username, meminfo.vms, ioinfo.write_bytes)
            except Exception, e:
                logger.error('Error crawling metric for process %s' % pid, exc_info=True)
                if not self.ignore_exceptions:
                    raise CrawlException(e)
    
    # crawl Linux package database
    def crawl_packages(self, dbpath=None, root_dir='/'):
        # package attributes: ["installed", "name", "size", "version"]
        (installtime, name, version, size) = (None, None, None, None)
        if self.crawl_mode == 'INVM': 
            logger.debug('Using in-VM state information (crawl mode: ' + self.crawl_mode + ')')
            system_type = platform.system().lower()
            distro = platform.linux_distribution()[0].lower() 
        elif self.crawl_mode == 'MOUNTPOINT': 
            logger.debug('Using disk image information (crawl mode: ' + self.crawl_mode + ')')
            system_type = platform_outofband.system(prefix=root_dir).lower()
            distro = platform_outofband.linux_distribution(prefix=root_dir)[0].lower()
        else:
            logger.error('Unsupported crawl mode: ' + self.crawl_mode + '. Skipping package crawl.')
            system_type = 'unknown'
            distro = 'unknown'

        installed_since = self.feature_epoch
        if system_type != 'linux':
            raise StopIteration() # package feature is only valid for Linux platforms
        logger.debug('Crawling Packages')
        
        pkg_manager = 'unknown'
        if distro in ['ubuntu', 'debian']:
            pkg_manager = 'dpkg'
        elif distro.startswith('red hat') or distro in ['redhat', 'fedora', 'centos']:
            pkg_manager = 'rpm'
        elif os.path.exists(os.path.join(root_dir, 'var/lib/dpkg')):
            pkg_manager = 'dpkg'
        elif os.path.exists(os.path.join(root_dir, 'var/lib/rpm')):
            pkg_manager ='rpm'
                
        try:
            if pkg_manager == 'dpkg':
                if not dbpath:
                    dbpath = 'var/lib/dpkg'
                if os.path.isabs(dbpath):
                    logger.warning("dbpath: " + dbpath + " is defined absolute. Crawler will ignore prefix: " + root_dir + ".")
                dbpath = os.path.join(root_dir, dbpath) #update for a different route
                if installed_since > 0:
                    logger.warning('dpkg does not provide install-time, defaulting to all packages installed since epoch')
                try:
                    dpkg = subprocess.Popen(["dpkg-query", "-W",
                               "--admindir={0}".format(dbpath),
                               "-f=${Package}|${Version}|${Installed-Size}\n"],
                               stdout=subprocess.PIPE)
                    dpkglist = dpkg.stdout.read().strip('\n')
                except OSError, e:
                    logger.error('Failed to launch dpkg query for packages. Check if dpkg-query is installed: ' 
                                 + ('[Errno: %d] ' % e.errno) + e.strerror + ' [Exception: ' + type(e).__name__ + ']')
                    dpkglist = None
                if dpkglist:
                    for dpkginfo in dpkglist.split('\n'):
                        (name, version, size) = dpkginfo.split('|')
                        # NOTE: dpkg does not provide any installtime field
                        #default_key = '{0}/{1}'.format(name, version) --> changed to below per Suriya's request
                        default_key = '{0}'.format(name, version)
                        yield default_key, PackageFeature(None, name, size, version)
            elif pkg_manager == 'rpm':
                if not dbpath:
                    dbpath = 'var/lib/rpm'
                if os.path.isabs(dbpath):
                    logger.warning("dbpath: " + dbpath + " is defined absolute. Crawler will ignore prefix: " + root_dir + ".")
                dbpath = os.path.join(root_dir, dbpath) #update for a different route
                try:
                    rpm = subprocess.Popen(["rpm", "--dbpath", dbpath,
                                "-qa", "--queryformat",
                                "%{installtime}|%{name}|%{version}|%{size}\n"],
                                stdout=subprocess.PIPE)
                    rpmlist = rpm.stdout.read().strip('\n')
                except OSError, e:
                    logger.error('Failed to launch rpm query for packages. Check if rpm is installed: ' 
                                 + ('[Errno: %d] ' % e.errno) + e.strerror + ' [Exception: ' + type(e).__name__ + ']')
                    rpmlist = None
                if rpmlist:
                    for rpminfo in rpmlist.split('\n'):
                        (installtime, name, version, size) = rpminfo.split('|')
                        # if int(installtime) <= installed_since: 
                        # --> this barfs for sth like: 1376416422. Consider try: xxx except ValueError: pass
                        if installtime <= installed_since:
                            continue
                        #default_key = '{0}/{1}'.format(name, version) --> changed to below per Suriya's request
                        default_key = '{0}'.format(name, version)
                        yield default_key, PackageFeature(installtime, name, size, version)
            else:
                raise CrawlException(Exception("Unsupported package manager for Linux distro %s" % distro))
        except Exception, e:
            logger.error('Error crawling package %s' % (name if name else "Unknown"), exc_info=True)
            if not self.ignore_exceptions:
                raise CrawlException(e)


    # Find the mount point of the specified cgroup
    def get_cgroup_dir(self, dev=""):
        paths = [os.path.join("/cgroup/", dev),
                 os.path.join("/sys/fs/cgroup/", dev)]
        for p in paths:
            if os.path.ismount(p):
                return p
        # Try getting the mount point from /proc/mounts
        try:
            proc = subprocess.Popen(
                "grep \"cgroup/" + dev + " \" /proc/mounts | awk '{print $2}'",
                shell=True, stdout=subprocess.PIPE)
            return proc.stdout.read().strip()
        except Exception, e:
            logger.exception(e)
            raise


    # crawl virtual memory information
    def crawl_memory(self, mountpoint=None):
        # memory attributes: ["used", "buffered", "cached", "free"]
        logger.debug('Crawling memory')
        feature_key = "memory"

        if self.crawl_mode == 'INVM': 
            try: used = psutil.virtual_memory().used
            except Exception, e: used = 'unknown'
            try: buffered = psutil.virtual_memory().buffers
            except Exception, e: buffered = 'unknown'
            try: cached = psutil.virtual_memory().cached
            except Exception, e: cached = 'unknown'
            try: free = psutil.virtual_memory().free
            except Exception, e: free = 'unknown'

            feature_attributes = MemoryFeature(used, buffered, cached, free)

        elif self.crawl_mode == 'OUTVM':
            domain_name, kernel_version, distro, arch = self.vm
            from psvmi import system_info
            sys = system_info(domain_name, kernel_version, distro, arch)
            feature_attributes = MemoryFeature(sys.memory_used,
                sys.memory_buffered, sys.memory_cached, sys.memory_free)

        elif self.crawl_mode == 'OUTCONTAINER':
            container_long_id = self.container_long_id
            used = buffered = cached = free = 'unknown'
            try:
                d = os.path.join(self.get_cgroup_dir("memory"), "docker",
                        container_long_id, "memory.stat")
                with open(d, "r") as f:
                    for line in f:
                        key, value = line.strip().split(' ')
                        if key == 'total_cache': cached = int(value)
                        if key == 'total_active_file': buffered = int(value)

                d = os.path.join(self.get_cgroup_dir("memory"), "docker",
                        container_long_id, "memory.limit_in_bytes")
                with open(d, "r") as f:
                    limit = int(f.readline().strip())

                d = os.path.join(self.get_cgroup_dir("memory"), "docker",
                        container_long_id, "memory.usage_in_bytes")
                with open(d, "r") as f:
                    used = int(f.readline().strip())

                host_free = psutil.virtual_memory().free

                container_total = used + min(host_free, limit - used)
                free = container_total - used
                feature_attributes = MemoryFeature(used, buffered, cached, free)

            except Exception, e:
                logger.error('Error crawling memory', exc_info=True)
                if not self.ignore_exceptions:
                    raise CrawlException(e)
                return

        else:
            logger.error('Unsupported crawl mode: ' + self.crawl_mode +
                         '. Returning unknown memory key and attributes.')
            feature_attributes = MemoryFeature('unknown', 'unknown',
                                               'unknown', 'unknown')
        try:
            yield feature_key, feature_attributes
        except Exception, e:
            logger.error('Error crawling memory', exc_info=True)
            if not self.ignore_exceptions:
                raise CrawlException(e)


    """
    Static cache of cpu_times. This is needed because for container cgroups
    we only get the total accumulated cpu time spent in a container. Then,
    to get a percentage utilization we need to have two cpu measurements.
    Instead of sleeping between the two measurements we use the previous
    crawled values. We use these variables to store those previous values.
    XXX Issue #272 need to be careful about this when we parallelize the crawls
    """
    container_cpu_times = dict()
    container_last_crawl_time = dict()

    @staticmethod
    def save_container_cpu_times(container_long_id, times):
        Crawler.container_cpu_times[container_long_id] = times
        now = time.time()
        Crawler.container_last_crawl_time[container_long_id] = now

    @staticmethod
    def get_prev_container_cpu_times(container_long_id):
        if Crawler.container_cpu_times.has_key(container_long_id):
            return [Crawler.container_cpu_times[container_long_id],
                    Crawler.container_last_crawl_time[container_long_id]]
        else:
            return [None, None]


    # crawl per CPU information
    def crawl_cpu(self, mountpoint=None, per_cpu=False):
        # cpu attributes: ["idle", "nice", "user", "wait", "system", "interrupt", "steal"]
        logger.debug('Crawling cpu information')

        if self.crawl_mode not in ['INVM', 'OUTCONTAINER', 'OUTVM']:
            logger.error('Unsupported crawl mode: ' + self.crawl_mode +
                         '. Returning unknown memory key and attributes.')
            feature_attributes = CpuFeature('unknown', 'unknown', 'unknown', 'unknown',
                                            'unknown', 'unknown', 'unknown')

        host_cpu_feature = {}
        if self.crawl_mode in ['INVM', 'OUTCONTAINER']:
            for index, cpu in enumerate(psutil.cpu_times_percent(percpu=True)):

                try: idle = cpu.idle
                except Exception, e: idle = 'unknown'
                try: nice = cpu.nice
                except Exception, e: nice = 'unknown'
                try: user = cpu.user
                except Exception, e: user = 'unknown'
                try: wait = cpu.iowait
                except Exception, e: wait = 'unknown'
                try: system = cpu.system
                except Exception, e: system = 'unknown'
                try: interrupt = cpu.irq
                except Exception, e: interrupt = 'unknown'
                try: steal = cpu.steal
                except Exception, e: steal = 'unknown'

                default_key = '{0}-{1}'.format("cpu", index)
                feature_attributes = CpuFeature(idle, nice, user, wait,
                                                system, interrupt, steal)
                host_cpu_feature[index] = feature_attributes
                if self.crawl_mode == 'INVM':
                    try:
                        yield default_key, feature_attributes
                    except Exception, e:
                        logger.error('Error crawling cpu information', exc_info=True)
                        if not self.ignore_exceptions:
                            raise CrawlException(e)

        elif self.crawl_mode == 'OUTVM':
            # XXX dummy data
            default_key = 'cpu-0'
            feature_attributes = CpuFeature(10, 10, 10, 10, 10, 10, 10)
            try:
                yield default_key, feature_attributes
            except Exception, e:
                logger.error('Error crawling cpu information', exc_info=True)
                if not self.ignore_exceptions:
                    raise CrawlException(e)

        if self.crawl_mode == 'OUTCONTAINER':

            if per_cpu:
                filename = "cpuacct.usage_percpu"
            else:
                filename = "cpuacct.usage"

            container_long_id = self.container_long_id

            """
            1. We first try to get the previous CPU times but if this fails
               because thisis the first crawl we sleep for 100ms.
            """
            cpu_usage = {}
            try:
                cpu_usage_t1, prev_time = self.get_prev_container_cpu_times(
                                              container_long_id)

                if cpu_usage_t1:
                    logger.info("Using previous cpu times for container %s"
                                % (container_long_id))
                    interval = time.time() - prev_time

                if not cpu_usage_t1 or interval == 0:
                    logger.info("There are no previous cpu times for container %s"
                                " so we will be sleeping for 100 milliseconds"
                                % (container_long_id))

                    d = os.path.join(self.get_cgroup_dir("cpuacct"), "docker",
                            container_long_id, filename)
                    with open(d, "r") as f:
                        cpu_usage_t1= f.readline().strip().split(' ')
                    interval = 0.1 # sleep for 100ms
                    time.sleep(interval)

                d = os.path.join(self.get_cgroup_dir("cpuacct"), "docker",
                        container_long_id, filename)
                with open(d, "r") as f:
                    cpu_usage_t2= f.readline().strip().split(' ')
                # Store the cpu times for the next crawl
                self.save_container_cpu_times(container_long_id, cpu_usage_t2)
            except Exception, e:
                logger.error('Error crawling cpu information', exc_info=True)
                if not self.ignore_exceptions:
                    raise CrawlException(e)
                return


            """
            2. get container system and user usage to split the per CPU usage
               time accordingly. This is just an approximation!
            """
            cpu_user_system = {}
            try:
                d = os.path.join(self.get_cgroup_dir("cpuacct"), "docker",
                        container_long_id, "cpuacct.stat")
                with open(d, "r") as f:
                    for line in f:
                        m = re.search(r"(system|user)\s+(\d+)", line)
                        if m:
                            cpu_user_system[m.group(1)] = float(m.group(2))
            except Exception, e:
                logger.error('Error crawling cpu information', exc_info=True)
                if not self.ignore_exceptions:
                    raise CrawlException(e)
                return


            """
            3. Approximations:
               1. user and system per cpu percentages are approximated using the
                  container cpu usage and the container user versus sustem time for
                  all the cpus of the container.
               2. nice, wait, interrupt, and steal are just host values.
            """
            for index, cpu_usage_ns in enumerate(cpu_usage_t1):
                usage_secs = ((float(cpu_usage_t2[index]) - float(cpu_usage_ns))
                                 / float(1e9))
                # Interval is never 0 because of step 0 (forcing a sleep)
                usage_percent = (usage_secs / interval) * 100.0
                if usage_percent > 100.0: usage_percent = 100.0
                idle = 100.0 - usage_percent
                # Approximation 1
                user_plus_sys_hz = (cpu_user_system['user'] +
                                    cpu_user_system['system'])
                if (user_plus_sys_hz == 0):
                    user_plus_sys_hz = 0.1  # Fake value to avoid divide by zero
                user = usage_percent * (cpu_user_system['user'] / user_plus_sys_hz)
                system = usage_percent * (cpu_user_system['system'] / user_plus_sys_hz)
                # Approximation 2
                nice = host_cpu_feature[index][1]
                wait = host_cpu_feature[index][3]
                interrupt = host_cpu_feature[index][5]
                steal = host_cpu_feature[index][6]
                default_key = '{0}-{1}'.format("cpu", index)
                feature_attributes = CpuFeature(idle, nice, user, wait,
                                                system, interrupt, steal)
                try:
                    yield default_key, feature_attributes
                except Exception, e:
                    logger.error('Error crawling cpu information', exc_info=True)
                    if not self.ignore_exceptions:
                        raise CrawlException(e)

    temp_changes_to_cache = {}
    def store_temp_change(self, key, value):
        self.temp_changes_to_cache[key] = value
    def get_temp_changes(self):
        return self.temp_changes_to_cache

    cached_values = {}
    @staticmethod
    def cache_apply_changes(changes):
        if not changes:
            return
        for key,value in changes.iteritems():
            Crawler.cached_values[key] = value

    @staticmethod
    def cache_get_value(key):
        if Crawler.cached_values.has_key(key):
            return Crawler.cached_values[key]
        else:
            return None

    # crawl per network interface information
    def crawl_interface(self, mountpoint=None):
        # interface attributes: ["if_octets.tx", "if_octets.rx", "if_packets.tx", "if_packets.rx", "if_errors.tx", "if_errors.rx"]
        logger.debug('Crawling interface information')

        for ifname in psutil.net_io_counters(pernic=True):
            try:
                interface = psutil.net_io_counters(pernic=True)[ifname]
            except:
                continue

            try: bytes_sent = interface.bytes_sent
            except Exception, e: bytes_sent = 'unknown'
            try: bytes_recv = interface.bytes_recv
            except Exception, e: bytes_recv = 'unknown'

            try: packets_sent = interface.packets_sent
            except Exception, e: packets_sent = 'unknown'
            try: packets_recv = interface.packets_recv
            except Exception, e: packets_recv = 'unknown'

            try: errout = interface.errout
            except Exception, e: errout = 'unknown'
            try: errin = interface.errin
            except Exception, e: errin = 'unknown'

            default_key = '{0}-{1}'.format("interface", ifname)
            store_key = '{0}-{1}'.format(self.namespace, default_key)
            prev_time_key = '{0}-{1}-last_crawl'.format(
                                self.namespace, default_key)

            prev_count = self.cache_get_value(store_key)
            prev_time = self.cache_get_value(prev_time_key)
            curr_count = [bytes_sent, bytes_recv, packets_sent,
                          packets_recv, errout, errin]

            self.store_temp_change(store_key, curr_count)
            self.store_temp_change(prev_time_key, time.time())

            if prev_count and prev_time:
                d = time.time() - prev_time
                diff = [(a - b) / d for a, b in zip(curr_count, prev_count)]
            else:
                # first measurement
                diff = [0,0,0,0,0,0]

            feature_attributes = InterfaceFeature._make(diff)

            try:
                yield default_key, feature_attributes
            except Exception, e:
                logger.error('Error crawling interface information', exc_info=True)
                if not self.ignore_exceptions:
                    raise CrawlException(e)


    # crawl virtual system load (this is based on the libc getloadavg API)
    def crawl_load(self, mountpoint=None):
        # memory attributes: ["shortterm", "midterm", "longterm"]
        logger.debug('Crawling system load')
        feature_key = "load"

        try: shortterm = os.getloadavg()[0]
        except Exception, e: shortterm = 'unknown'
        try: midterm = os.getloadavg()[1]
        except Exception, e: midterm = 'unknown'
        try: longterm = os.getloadavg()[2]
        except Exception, e: longterm = 'unknown'

        feature_attributes = LoadFeature(shortterm, midterm, longterm)

        try:
            yield feature_key, feature_attributes
        except Exception, e:
            logger.error('Error crawling memory', exc_info=True)
            if not self.ignore_exceptions:
                raise CrawlException(e)


    def crawl_dockerps(self, mountpoint=None):
        logger.debug('Crawling docker ps results')

        # Let's try Docker API first
        try:
            from docker import Client
            client = Client(base_url='unix://var/run/docker.sock')
            container_long_id = self.container_long_id
            containers = client.containers()
            for c in containers:  # docker ps
                # time.strftime("%Y-%m-%dT%H:%M:%S%z",time.localtime(1429306125))
                yield c['Id'], c
            return
        except Exception, e:
            logger.error(e)

        # Docker API versioning is a mess, so now using the command directly
        proc = subprocess.Popen("docker ps -q", shell=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        short_ids = proc.stdout.read().split('\n')
        out, err = proc.communicate()
        if proc.returncode != 0:
            # There is no docker command (or it just failed).
            return

        # If you change this order, also change DockerPSFeature
        fmt = ('{{.State.Running}},{{.Created}},{{.Image}},'
               '{{.NetworkSettings}},{{.Config.Cmd}},{{.Name}},{{.Id}}')

        proc = subprocess.Popen(
            "docker inspect --format '" + fmt + "' %s" % " ".join(short_ids),
            shell=True, stdout=subprocess.PIPE)
        ll = proc.stdout.read().strip()
        long_list = ll.split('\n')
        for c in long_list:
            co = c.split(',')
            feature_key = co[6]
            co[1] = 0 # elastic search is not parsing this port string XXX
            co[3] = [] # elastic search is not parsing this datetime XXX
            feature_attributes = DockerPSFeature._make(co)
            try:
                yield feature_key, feature_attributes
            except Exception, e:
                logger.error('Error crawling dockerps', exc_info=True)
                if not self.ignore_exceptions:
                    raise CrawlException(e)


    DockerImageHistoryTuple = namedtuple('image', ["Tags", "Size", "Id", "CreatedBy", "Created"])

    def _get_docker_image_history(self, image_id):
        proc = subprocess.Popen(
            "docker history -q --no-trunc %s" % (image_id),
            shell=True, stdout=subprocess.PIPE)
        history_img_ids = proc.stdout.read().split()

        """
        XXX This is hacky. Docker inspect can dump multiple lines per record
        so we need some way of identifying the end of a record.
        """
        eor = "***ENDOFRECORD***"
        proc = subprocess.Popen(
                "docker inspect --format '{{.Tags}},{{.Size}},{{.Id}},"
                "{{.ContainerConfig.Cmd}},{{.Created}}%s' %s" % 
                    (eor, " ".join(history_img_ids)),
                shell=True, stdout=subprocess.PIPE)
        image_history = []
        for image in proc.stdout.read().split(eor):
            image_info = image.strip().replace('\n', ' ').replace('\r', '').split(',')
            if image_info != ['']:
                image_history.append(self.DockerImageHistoryTuple._make(image_info))
        return image_history


    def crawl_dockerhistory(self, mountpoint=None):
        logger.debug('Crawling docker history')

        long_id = self.container_long_id

        # Let's try Docker API first
        try:
            from docker import Client
            client = Client(base_url='unix://var/run/docker.sock')
            containers = client.containers()
            for c in containers:  # docker ps
                if not long_id or long_id == c['Id']:
                    yield c['Image'], {'history': client.history(c['Image'])}
            return
        except Exception, e:
            logger.error(e)

        # Docker API versioning is a mess, so let's call the command directly
        if not long_id:
            proc = subprocess.Popen("docker images -q --no-trunc", shell=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            all_image_ids = proc.stdout.read().split()
        else:
            proc = subprocess.Popen(
                "docker inspect --format {{.Image}} %s" % long_id,
                shell=True, stdout=subprocess.PIPE)
            ll = proc.stdout.read().strip()
            all_image_ids = ll.split('\n')

        for image_id in all_image_ids:
            try:
                history = self._get_docker_image_history(image_id)
                feature_key = image_id
                feature_attributes = DockerHistoryFeature._make([history])
                yield feature_key, feature_attributes
            except Exception, e:
                logger.error('Error crawling dockerhistory', exc_info=True)
                if not self.ignore_exceptions:
                    raise CrawlException(e)


    def _reformat_inspect(self,cjson):
        def fold_port_key(ports_dict):
            if not ports_dict:
                return None
            # map network settings in ports
            pd = []
            for k,v in ports_dict.iteritems():
                port, proto = (k, '') if not '/' in k else k.split('/') 
                if v:
                    for i in v:
                        i['Protocol'] = proto
                else:
                    v = [{ 'HostPort':port, 'HostIp':'', 'Protocol': proto}]
                pd.append(v)
            return pd

        np = fold_port_key(cjson['NetworkSettings']['Ports'])
        if np:
            cjson['NetworkSettings']['Ports'] = np

        np = fold_port_key(cjson['HostConfig']['PortBindings'])
        if np:
            cjson['HostConfig']['PortBindings'] = np


    def crawl_dockerinspect(self, mountpoint=None):
        logger.debug('Crawling docker inspect')

        long_id = self.container_long_id

        # Let's try Docker API first
        try:
            from docker import Client
            client = Client(base_url='unix://var/run/docker.sock')
            container_long_id = self.container_long_id
            containers = client.containers()
            for c in containers:  # docker ps
                if not long_id or long_id == c['Id']:
                    out = client.inspect_container(c['Id'])
                    self._reformat_inspect(out)
                    yield c['Id'], out
            return
        except Exception, e:
            logger.error(e)

        # Docker API versioning is a mess, so let's call the command directly
        proc = subprocess.Popen("docker ps --no-trunc -q", shell=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ids = proc.stdout.read().split()
        out, err = proc.communicate()
        if proc.returncode != 0:
            # There is no docker command (or it just failed).
            return

        long_id = self.container_long_id
        for id in ids:
            if long_id and long_id != id:
                continue
            try:
                proc = subprocess.Popen(
                    "docker inspect %s" % id,
                    shell=True, stdout=subprocess.PIPE)
                inspect_data = proc.stdout.read().strip()
                feature_key = id
                # XXX hacky, inspect returns a list of json's.
                # remove the '[' and ']' by hand (instead of calling eval().)
                inspect_data = inspect_data[1:]
                inspect_data = inspect_data[:-1]
                print inspect_data
                cjson = json.loads(inspect_data)
                self._reformat_inspect(cjson)
                feature_attributes = cjson
                yield feature_key, feature_attributes
            except Exception, e:
                logger.error('Error crawling dockerinspect', exc_info=True)
                raise
                if not self.ignore_exceptions:
                    raise CrawlException(e)


class DummyEmitter:
    def __init__(self, urls, url_args={}, compress=True,
                 max_features=sys.maxint, format="csv", max_emit_retries=5):
        pass
    def __enter__(self):
        return self
    def update_url_args(self, url_args):
        pass
    def emit(self, feature_key, feature_val, feature_type=None):
        pass
    def close_file(self):
        pass
    def flush_file(self):
        pass
    def __exit__(self, typ, exc, trc):
        pass

class Emitter:
    # We want to use a global to store the MTGraphite client class so it persists
    # across metric intervals
    mtgclient = None
    
    # Debugging TIP: use url='file://<local-file>' to emit the frame data into a local file
    def __init__(self, urls, url_args={}, compress=True,
                 max_features=sys.maxint, format="csv", max_emit_retries=5):

        self.urls = urls
        self.url_args = url_args
        self.compress = compress
        self.max_features = max_features
        self.format = format
        self.max_emit_retries = max_emit_retries
        self.mtgclient = None
 
    def __enter__(self):
        self.temp_fd, self.temp_fpath = tempfile.mkstemp(prefix='emit.')
        os.close(self.temp_fd) # close temmorary file descriptor
                               # as we open immediately
                               # need to find a better fix later
        if self.compress:
            self.emitfile = gzip.open(self.temp_fpath, 'wb')
        else:
            self.emitfile = open(self.temp_fpath, 'wb')
        self.csv_writer = csv.writer(self.emitfile, delimiter="\t", quotechar="'")
        self.begin_time = time.time()
        self.num_features = 0
        self.global_num_features = 0
        return self

    def update_url_args(self, url_args):
        self.url_args = url_args

    def _get_feature_type(self, feature):
        if isinstance(feature, OSFeature):
            return 'os'
        if isinstance(feature, FileFeature):
            return 'file'
        if isinstance(feature, ConfigFeature):
            return 'config'
        if isinstance(feature, DiskFeature):
            return 'disk'
        if isinstance(feature, ProcessFeature):
            return 'process'
        if isinstance(feature, ConnectionFeature):
            return 'connection'
        if isinstance(feature, MetricFeature):
            return 'metric'
        if isinstance(feature, PackageFeature):
            return 'package'
        if isinstance(feature, MemoryFeature):
            return 'memory'
        if isinstance(feature, CpuFeature):
            return 'cpu'
        if isinstance(feature, InterfaceFeature):
            return 'interface'
        if isinstance(feature, LoadFeature):
            return 'load'
        if isinstance(feature, DockerPSFeature):
            return 'dockerps'
        if isinstance(feature, DockerHistoryFeature):
            return 'dockerhistory'
        raise ValueError('Unrecognized feature type')

    def emit_dict_as_graphite(self, sysname, group, suffix, data, timestamp=None):
        if timestamp is None:
            timestamp = int(time.time())
        else:
            timestamp = int(timestamp)

        try:
            items = data.items()
        except:
            return

        # this is for issue #343
        sysname = sysname.replace('/', '.')

        for metric, value in items:
            try:
                value = float(value)
            except Exception, e:
                # value was not a float or anything that looks like a float
                continue

            """
            Make sure the metric is free of control chars, spaces, tabs, etc.
            """
            metric = metric.replace('(', '_').replace(')', '')
            metric = metric.replace(' ', '_').replace('-', '_')
            metric = metric.replace('/', '_').replace('\\', '_')

            """
            Make sure we match our metric names to what collectd emits.
            """
            suffix = suffix.replace('_', '-')
            if 'cpu' in suffix or 'memory' in suffix:
                metric = metric.replace('_', '-')
            if 'if' in metric:
                metric = metric.replace('_tx', '.tx')
                metric = metric.replace('_rx', '.rx')
            if suffix == 'load':
                suffix = 'load.load'

            tmp_message = "%s.%s.%s %f %d\r\n" % (sysname, suffix,
                                                  metric, value, timestamp)
            self.emitfile.write(tmp_message)
        return

    #Added optional feature_type so that we can bypass feature type discovery for FILE crawlmode
    def emit(self, feature_key, feature_val, feature_type=None):
        # Add metadata as first feature
        if self.num_features == 0:
            try:
                metadata = copy.deepcopy(self.url_args)
                # Update timestamp to the actual emit time
                metadata['timestamp'] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
                del metadata['extra']
                del metadata['extra_all_features']
                if self.url_args['extra']:
                    metadata.update(json.loads(self.url_args['extra']))
                if self.format == "csv":
                    self.csv_writer.writerow(["metadata", json.dumps("metadata"), json.dumps(metadata, separators=(',',':'))])
                    self.num_features += 1
                    self.global_num_features += 1
            except Exception, e:
                logger.exception(e)
                raise

        if (self.num_features < self.max_features and
            self.global_num_features < self.max_features):
            if feature_type == None:
                feature_type = self._get_feature_type(feature_val)
            if isinstance(feature_val, dict):
                feature_val_as_dict = feature_val
            else:
                feature_val_as_dict = feature_val._asdict()
            if (self.url_args['extra'] and
                self.url_args['extra_all_features'] == True):
                feature_val_as_dict.update(json.loads(self.url_args['extra']))
            try:
                if self.format == "csv":
                    self.csv_writer.writerow([feature_type, json.dumps(feature_key), json.dumps(feature_val_as_dict, separators=(',',':'))])
                elif self.format == "graphite":
                    self.emit_dict_as_graphite(self.url_args['namespace'], feature_type, feature_key, feature_val_as_dict)
                else:
                    raise Exception("Unsupported emitter format.")
                self.num_features += 1
                self.global_num_features += 1
            except Exception, e:
                logger.exception(e)
                raise

    def close_file(self):
        # close the output file
        self.emitfile.close()

    def flush_file(self):
        # flush the output file buffer
        self.emitfile.flush()

    def _publish_to_broker(self, url, max_emit_retries=5):
        # try contacting the broker
        broker_alive = False
        retries = 0
        while (not broker_alive and retries <= max_emit_retries):
            try:
                retries += 1
                response = requests.get(url)
                broker_alive = True
            except Exception, e:
                if retries <= max_emit_retries:
                    # Wait for (2^retries * 100) milliseconds
                    wait_time = (2.0**retries) * 0.1
                    logger.error("Could not connect to the broker at %s."
                                 "Retry in %f seconds." % (url, wait_time))
                    time.sleep(wait_time)
                else:
                    raise

        with open(self.temp_fpath, 'rb') as framefp:
            headers = {'content-type': 'text/csv'}
            if self.compress:
                headers['content-encoding'] = 'gzip'
            try:
                response = requests.post(url, headers=headers,
                                         params=self.url_args, data=framefp)
            except Exception, e:
                logger.error("Could not connect to the broker at %s " % url)
                raise


    #@timeout(5)
    def _publish_to_kafka_no_retries(self, url):

        try:
            list = url[len('kafka://'):].split('/')

            if len(list) == 2:
                kurl = list[0]
                topic = list[1]
            else:
                raise Exception("The kafka url provided does not seem to "
                    " be valid: %s. It should be something like this:"
                    " kafka://[ip|hostname]:[port]/[kafka_topic]. For example:"
                    " kafka://1.1.1.1:1234/alchemy_metrics" % (url))

            from kafka import KafkaClient, SimpleProducer, KeyedProducer
            kafka = KafkaClient(kurl)

            if self.format == 'csv':
                producer = SimpleProducer(kafka)
                producer.client.ensure_topic_exists(topic)
                with open(self.temp_fpath, 'r') as fp:
                    text = fp.read()
                    logger.debug(producer.send_messages(topic, text))
                producer.stop()

            elif self.format == 'graphite':
                """
                kafka-graphite expects our records to be sent one at a time.
                Also, at high latencies, this can result in many round-trips
                which can severly degrade throughput. Because of this, we use
                batching. Notice that this can hurt us if the message is too
                big so we don't use batching for the csv format.
                """
                producer = SimpleProducer(kafka, batch_send=True,
                                          batch_send_every_n=100,
                                          batch_send_every_t=20)
                producer.client.ensure_topic_exists(topic)
                with open(self.temp_fpath, 'r') as fp:
                    for line in fp.readlines():
                        #logger.debug(topic + ": " + line)
                        producer.send_messages(topic, line)
                producer.stop()
            else:
                logger.debug('Could not send data because {0} is an unknown '
                             'format'.format(self.format))
                raise
            kafka.close()
        except Exception, e:
            logger.debug('Could not send data to {0}: {1}'.format(url, e))
            raise


    def _publish_to_kafka(self, url, max_emit_retries=5):
        broker_alive = False
        retries = 0
        while (not broker_alive and retries <= max_emit_retries):
            try:
                retries += 1
                self._publish_to_kafka_no_retries(url)
                broker_alive = True
            except Exception, e:
                if retries <= max_emit_retries:
                    # Wait for (2^retries * 100) milliseconds
                    wait_time = (2.0**retries) * 0.1
                    logger.error("Could not connect to the kafka server at %s."
                                 "Retry in %f seconds." % (url, wait_time))
                    time.sleep(wait_time)
                else:
                    raise


    def _publish_to_mtgraphite(self, url):
        if not Emitter.mtgclient:
            Emitter.mtgclient = MTGraphiteClient(url)
        with open(self.temp_fpath, 'r') as fp:
            num_pushed_to_queue = Emitter.mtgclient.send_messages(fp.readlines())
            logger.debug("Pushed %d messages to mtgraphite queue" % num_pushed_to_queue)


    def _write_to_file(self, url):
        output_path = url[len('file://'):]
        if self.compress:
            output_path += '.gz' 
        shutil.move(self.temp_fpath, output_path)

    def __exit__(self, typ, exc, trc):
        if exc:
            self.close_file()
            if os.path.exists(self.temp_fpath):
                os.remove(self.temp_fpath)
            return False
        try:
            self.close_file()
            for url in self.urls:
                logger.debug('Emitting frame to {0}'.format(url))
                if url.startswith('http://'):
                    self._publish_to_broker(url, self.max_emit_retries)
                elif url.startswith('file://'):
                    self._write_to_file(url)
                elif url.startswith('kafka://'):
                    self._publish_to_kafka(url, self.max_emit_retries)
                elif url.startswith('mtgraphite://'):
                    self._publish_to_mtgraphite(url)
                else:
                    if os.path.exists(self.temp_fpath):
                        os.remove(self.temp_fpath)
                    raise ValueError('Unsupported URL protocol {0}'.format(url))
        except Exception, e:
            logger.exception(e)
            raise
        finally:
                if os.path.exists(self.temp_fpath):
                    os.remove(self.temp_fpath)
        self.end_time = time.time()
        elapsed_time = self.end_time - self.begin_time
        logger.info('Emitted {0} features in {1} seconds'.format(self.num_features, elapsed_time))
        return False    


# Find the mountpoint of a given path
def find_mount_point(path):
    path = os.path.abspath(path)
    while not os.path.ismount(path):
        path = os.path.dirname(path)
    return path

# Log the atime configuration of the mount location of the given path
# Return: 'unknown' | 'strictatime' | 'relatime' | 'noatime'
def log_atime_config(path,crawlmode):
    atime_config = 'unknown'
    mountlocation = find_mount_point(path=path) 
    logger.info("Mount location for specified crawl root_dir '%s': '%s'" % (path,mountlocation))
    # Looking at `mount` for atime config is only meaningful for INVM 
    if crawlmode == 'INVM':
        grepstr='on %s ' % mountlocation
        try:
            mount = subprocess.Popen(('mount'), stdout=subprocess.PIPE)
            mountlist = subprocess.Popen(('grep', grepstr), stdin=mount.stdout,
                                         stdout=subprocess.PIPE)
            mountlist_arr = mountlist.stdout.read().split('\n')
            if len(mountlist_arr) > 0:
                # pick the first one if we found more than one mount location
                # Will look like: "/dev/xvda2 on / type ext3 (rw,noatime,errors=remount-ro,barrier=0)"
                ptrn=r'.*?\((.*?)\).*?'
                match = re.search(ptrn,mountlist_arr[0])
                # Get the part in parenthesis and split. WIll look like: "rw,noatime,errors=remount-ro,barrier=0"
                for i in match.group(1).split(','):
                    if i.strip() == 'noatime':
                        atime_config = 'noatime'
                        logger.debug('Found atime config: %s in mount information, updating log' % atime_config)
                        break
                    elif i.strip() == 'relatime':
                        atime_config = 'relatime'
                        logger.debug('Found atime config: %s in mount information, updating log' % atime_config)
                        break
                    elif i.strip() == 'strictatime':
                        atime_config = 'strictatime'
                        logger.debug('Found atime config: %s in mount information, updating log' % atime_config)
                        break
                # If we found a mount location, but did not have atime info in mount. Assume it is the default relatime. 
                # As it does not show in mount options by default. 
                if atime_config == 'unknown':
                        atime_config = 'relatime'
                        logger.debug('Did not find any atime config for the matching mount location. Assuming: %s' % atime_config)
        except OSError, e:
            logger.error('Failed to query mount information: ' 
                         + ('[Errno: %d] ' % e.errno) + e.strerror + ' [Exception: ' + type(e).__name__ + ']')

    logger.info("Atime configuration for '%s': '%s'" % (mountlocation,atime_config))
    if atime_config == 'strictatime':
        logger.info('strictatime: File access times are reflected correctly')
    if atime_config == 'relatime':
        logger.info('relatime: File access times are only updated after 24 hours')
    if atime_config == 'noatime':
        logger.info('noatime: File access times are never updated properly')
    if atime_config == 'unknown':
        logger.info('unknown: Could not determine atime config. File atime information might not be reliable')
    return atime_config

DEFAULT_FEATURES_TO_CRAWL = 'os,disk,process,package,config,file'
#DEFAULT_FEATURES_TO_CRAWL = 'os,disk,process,connection,file,package,config'
#DEFAULT_FEATURES_TO_CRAWL = 'os,disk,file,package,config'

DEFAULT_CRAWL_OPTIONS = {
    'os': {},
    'disk': {},
    'package': {},
    'process': {},
    'metric': {},
    'connection': {},
    'file': {'root_dir': '/', 'exclude_dirs': ['boot', 'dev', 'proc', 'sys', 'mnt', 'tmp', 'var/cache', 'usr/share/man', 'usr/share/doc', 'usr/share/mime']},
    'config': {'root_dir':'/', 'exclude_dirs': ['dev', 'proc', 'mnt', 'tmp', 'var/cache', 'usr/share/man', 'usr/share/doc', 'usr/share/mime'], 
               'known_config_files': ['etc/passwd', 'etc/group', 'etc/hosts', 'etc/hostname', 
                                      'etc/mtab', 'etc/fstab', 'etc/aliases', 'etc/ssh/ssh_config', 
                                      'etc/sudoers'], 
               'discover_config_files': True},
    'memory': {},
    'interface': {},
    'cpu': {},
    'load': {},
    'dockerps': {},
    'dockerhistory': {},
    'dockerinspect': {},
    'logcrawler': {'host_log_basedir':'/var/log/crawler_container_logs/',
                   'container_logs_list_file':'/etc/logcrawl-logs.json',
                   'default_log_files': ['/var/log/messages']},
    'metadata': {'namespace_map': {}}
}

def snapshot_single_frame(emitter, featurelist, options, crawler):
    #Special-casing Reading from a frame file as input here: 
    #- Sweep through entire file, if feature.type is in featurelist, emit feature.key and feature.value
    #- Emit also validates schema as usual, so do not try to pass noncomplicant stuff in the input frame file; it will bounce.
    crawlmode = crawler.crawl_mode
    if crawlmode == 'FILE':
        logger.debug('Reading features from local frame file {0}'.format(inputfile)) 
        FeatureFormat = namedtuple('FeatureFormat', ['type', 'key', 'value'])
        if (inputfile is None) or (not os.path.exists(inputfile)):
            logger.error('Input frame file: ' + inputfile + ' does not exist.')
        with open(inputfile, 'r') as fd:
            csv.field_size_limit(sys.maxsize) # to handle large values
            csv_reader = csv.reader(fd, delimiter='\t', quotechar="'")
            num_features = 0
            for row in csv_reader:
                feature_data = FeatureFormat(row[0], json.loads(row[1]), json.loads(row[2], object_pairs_hook=OrderedDict))
                #print 'feature.type:', feature_data.type, '\nfeature.key:', feature_data.key, '\nfeature.value:', feature_data.value
                num_features += 1
                # Emit only if in the specified features-to-crawl list
                if feature_data.type in featurelist:
                    emitter.emit(feature_data.key, feature_data.value, feature_data.type)
            logger.info('Read %d feature rows from %s' % (num_features,inputfile))
    else:
        t = 0
        for ftype in featurelist:
            fopts = options.get(ftype, DEFAULT_CRAWL_OPTIONS.get(ftype, None))
            if fopts is None:
                continue
            if ftype == 'os':
                for key, feature in crawler.crawl_os(**fopts):
                    emitter.emit(key, feature)
            if ftype == 'disk':
                if crawlmode == 'INVM':
                    for key, feature in crawler.crawl_disk_partitions(**fopts):
                        emitter.emit(key, feature)
                else:
                    logger.warning("Cannot crawl feature: " + ftype + " in crawl mode: " + crawlmode + ". Skipping..." )
            if ftype == 'metric':
                if crawlmode == 'INVM':
                    for key, feature in crawler.crawl_metrics(**fopts):
                        emitter.emit(key, feature)
                else:
                    logger.warning("Cannot crawl feature: " + ftype + " in crawl mode: " + crawlmode + ". Skipping..." )
            if ftype == 'process':
                if crawlmode in ['INVM', 'OUTVM']:
                    for key, feature in crawler.crawl_processes(**fopts):
                        emitter.emit(key, feature)
                else:
                    logger.warning("Cannot crawl feature: " + ftype + " in crawl mode: " + crawlmode + ". Skipping..." )
            if ftype == 'connection':
                if crawlmode in ['INVM', 'OUTVM']:
                    for key, feature in crawler.crawl_connections(**fopts):
                        emitter.emit(key, feature)
                else:
                    logger.warning("Cannot crawl feature: " + ftype + " in crawl mode: " + crawlmode + ". Skipping..." )
            if ftype == 'package':
                for key, feature in crawler.crawl_packages(**fopts):
                    emitter.emit(key, feature)
            if ftype == 'file':
                for key, feature in crawler.crawl_files(**fopts):
                    emitter.emit(key, feature)
            if ftype == 'config':
                for key, feature in crawler.crawl_config_files(**fopts):
                    emitter.emit(key, feature)
            if ftype == 'memory':
                if crawlmode in ['INVM', 'OUTVM', 'OUTCONTAINER']:
                    for key, feature in crawler.crawl_memory(**fopts):
                        emitter.emit(key, feature)
                else:
                    logger.warning("Cannot crawl feature: " + ftype + " in crawl mode: " + crawlmode + ". Skipping..." )
            if ftype == 'cpu':
                if crawlmode in ['INVM', 'OUTVM']:
                    fopts['per_cpu'] = True
                    for key, feature in crawler.crawl_cpu(**fopts):
                        emitter.emit(key, feature)
                if crawlmode in ['OUTCONTAINER']:
                    fopts['per_cpu'] = False
                    for key, feature in crawler.crawl_cpu(**fopts):
                        emitter.emit(key, feature)
                else:
                    logger.warning("Cannot crawl feature: " + ftype + " in crawl mode: " + crawlmode + ". Skipping..." )
            if ftype == 'interface':
                if crawlmode == 'INVM':
                    for key, feature in crawler.crawl_interface(**fopts):
                        emitter.emit(key, feature)
                else:
                    logger.warning("Cannot crawl feature: " + ftype + " in crawl mode: " + crawlmode + ". Skipping..." )
            if ftype == 'load':
                if crawlmode == 'INVM':
                    for key, feature in crawler.crawl_load(**fopts):
                        emitter.emit(key, feature)
                else:
                    logger.warning("Cannot crawl feature: " + ftype + " in crawl mode: " + crawlmode + ". Skipping..." )
            if ftype == 'dockerps':
                if crawlmode in ['INVM', 'OUTCONTAINER']:
                    for key, feature in crawler.crawl_dockerps(**fopts):
                        emitter.emit(key, feature, 'dockerps')
                else:
                    logger.warning("Cannot crawl feature: " + ftype + " in crawl mode: " + crawlmode + ". Skipping..." )
            if ftype == 'dockerhistory':
                if crawlmode in ['INVM', 'OUTCONTAINER']:
                    for key, feature in crawler.crawl_dockerhistory(**fopts):
                        emitter.emit(key, feature, 'dockerhistory')
                else:
                    logger.warning("Cannot crawl feature: " + ftype + " in crawl mode: " + crawlmode + ". Skipping..." )
            if ftype == 'dockerinspect':
                if crawlmode in ['INVM', 'OUTCONTAINER']:
                    for key, feature in crawler.crawl_dockerinspect(**fopts):
                        emitter.emit(key, feature, 'dockerinspect')
                else:
                    logger.warning("Cannot crawl feature: " + ftype + " in crawl mode: " + crawlmode + ". Skipping..." )


def process_is_crawler(proc):
    try:
        cmdline = (proc.cmdline() if hasattr(proc.cmdline, '__call__')
                   else proc.cmdline)
        # curr is this crawler process
        curr = psutil.Process(os.getpid())
        curr_cmdline = (curr.cmdline() if hasattr(
                        curr.cmdline, '__call__') else curr.cmdline)
        if cmdline == curr_cmdline:
            return True
    except:
        pass
    return False


def get_pid_namespace(pid):
    try:
        ns = os.stat("/proc/" + str(pid) + "/ns/pid").st_ino
        return ns
    except Exception, e:
        logger.debug("The container with pid=%s is not present anymore" % pid)
        return None


# Per process cache of docker inspect details
docker_inspect_cache = dict()

# returns a list of (pid, short_docker_id, long_docker_id, name, image)
def list_docker_containers(user_list):
    global docker_inspect_cache

    # If there are no containers, the only pid returned would be "1" (init)
    logger.info("User specified list of containers to crawl: %s" % (user_list))
    if user_list == "" or not user_list:
        return

    # Docker API versioning is a mess, so let's call the command directly
    proc = subprocess.Popen("docker ps -q", shell=True,
                            stdout=subprocess.PIPE)
    short_id_list = proc.stdout.read().strip().split()

    all_docker_containers = []
    missing_short_id_list = []
    for short_id in short_id_list:
        if docker_inspect_cache.has_key(short_id):
            c = docker_inspect_cache[short_id]
            if get_pid_namespace(c.pid):
                all_docker_containers.append(c)
            else:
                del docker_inspect_cache[short_id]
                missing_short_id_list.append(short_id)
        else:
            missing_short_id_list.append(short_id)

    if missing_short_id_list:
        missing_ids_string = " ".join(missing_short_id_list).strip()
        proc = subprocess.Popen(
                "docker inspect --format '{{.State.Pid}}' %s" % missing_ids_string,
                shell=True, stdout=subprocess.PIPE)
        pid_list = proc.stdout.read().split()
        # Docker sometimes returns pids in scientific notation
        pid_list = ["%.0f" % float(x) for x in pid_list]
        proc = subprocess.Popen(
                "docker inspect --format '{{.Id}}' %s" % missing_ids_string,
                shell=True, stdout=subprocess.PIPE)
        long_id_list = proc.stdout.read().split()
        proc = subprocess.Popen(
                "docker inspect --format '{{.Name}}' %s" % missing_ids_string,
                shell=True, stdout=subprocess.PIPE)
        name_list = proc.stdout.read().split()
        proc = subprocess.Popen(
                "docker inspect --format '{{.Image}}' %s" % missing_ids_string,
                shell=True, stdout=subprocess.PIPE)
        image_list = proc.stdout.read().split()
        nested_lst = [list(x) for x in
            zip(pid_list, missing_short_id_list, long_id_list,
                name_list, image_list)]
	all_docker_containers.extend([Container(*l, namespace=None) for l in nested_lst])
    logger.info("All docker containers running: %s" % (all_docker_containers))

    for c in all_docker_containers:
        # cache the details we got from inspect
        docker_inspect_cache[c.short_id] = c
        yield c


"""
If user_list is "ALL" or None: List all running containers
If user_list is a list string: Only return containers in the list

If not a docker container, the short_id is hash(pid)
"""
def list_all_containers(user_list):

    all_docker_containers = list_docker_containers(user_list)

    if user_list in ["ALL", "all", "All"]:
        """
        We should not list the host as a container, so we make
        sure that none of the containers we get have the same
        namespace as the host init process.
        """
        init_ns = get_pid_namespace(1)

        visited_ns = set() # visited PID namespaces

        # Start with all docker containers
        for c in all_docker_containers:
            curr_ns = get_pid_namespace(c.pid)
            if not curr_ns:
                continue
            if (curr_ns not in visited_ns and
                    curr_ns != init_ns):
                visited_ns.add(curr_ns)
                yield c

        # Continue with all other containers not known to docker
        for p in psutil.process_iter():
            pid = p.pid() if hasattr(p.pid, '__call__') else p.pid
            if process_is_crawler(p):
                # don't confuse the crawler process with a container
                continue
            curr_ns = get_pid_namespace(pid)
            if not curr_ns:
                # invalid container
                continue
            if (curr_ns not in visited_ns and
                    curr_ns != init_ns):
                visited_ns.add(curr_ns)
                yield Container(str(pid), str(hash(pid)), None, str(pid), None, None)
    else:
        # User provided a list of containers
        user_containers = user_list.split(',')
        for c in all_docker_containers:
            if c.short_id in user_containers:
                yield c


def GetProcessEnv(pid=1):
    """the environment settings from the processes perpective,
       @return C{dict}
    """
    env = {}
    try: envlist = open('/proc/%s/environ' % pid).read().split('\000')
    except: return env
    for e in envlist:
	if '=' in e:
	    k,v = e.split('=',1)
	else:
	    k,v = e,''
	k,v = k.strip(),v.strip()
	if not k: continue
	env[k] = v
    return env


def get_container_log_files(c, rootfs_path, container_logs_list_file="/etc/logcrawl-logs.json"):
    container_logs_list = []
    log_locations = []

    # 1. Get the log files from an env variable
    try:
        log_locations = GetProcessEnv(c.pid)["LOG_LOCATIONS"].split(',')
    except KeyError, exc:
        logger.exception(exc)
        logger.warning("There is no LOG_LOCATIONS environment variable.")
        pass
    except IOError, exc:
        logger.exception(exc)
        pass
    except OSError, exc:
        logger.exception(exc)
        pass
    except Exception, e:
        logger.exception(e)
        raise

    # 2. Generate the container_logs_list
    json_path = rootfs_path + container_logs_list_file
    try:
        with open(json_path, 'r') as fp:
            data = json.loads(fp.read())
            log_locations.extend(data["log_files"])
    except json.JSONDecodeError, exc:
        logger.error("The container log file list %s is not a valid "
                     "json file." % json_path)
        logger.exception(exc)
        pass
    except KeyError, exc:
        logger.exception(exc)
        logger.warning("There is no log_files entry in the json container "
                       "log locations file.")
        pass
    except IOError, exc:
        logger.exception(exc)
        pass
    except OSError, exc:
        logger.exception(exc)
        pass
    except Exception, e:
        logger.exception(e)
        raise

    # Finally create the list of log locations
    for line in log_locations:
        line = line.strip()
        if os.path.isabs(line) and ".." not in line:
            container_logs_list.append(line)
        else:
            logger.warning("User provided a log file path"
                           " that is not absolute: %s" % line)
    return container_logs_list


"""
Return the path in the host where the container
logs will be linked.
"""
def get_container_logs_dir(ctr_namespace, pid, short_id, long_id,
                           host_log_basedir, env='cloudsight'):
    if env == 'cloudsight':
        host_log_dir = os.path.join(host_log_basedir, ctr_namespace)
        return host_log_dir
    elif env == 'alchemy':
        if pid == "1":
            logger.info("get_ctr_namespace() returning None for pid=1 as "
                        "we do not want to crawl the host.")
            return None
        if not long_id:
            logger.info("Not crawling container with pid %s because it does"
                        " not seem to be a docker container." % (pid))
            return None
        else:
            from alchemy import get_logs_dir_on_host
            host_dir = get_logs_dir_on_host(long_id, "docker")
            if not host_dir:
                logger.info("Container %s does not have alchemy metadata."
                            % (short_id))
            host_log_dir = os.path.join(host_log_basedir, host_dir)
            return host_log_dir
    else:
        logger.error("Unknown environment %s" % (env))
        return None


"""
Return the path to the docker logs for the container
"""
def get_docker_container_logs_path(long_id):
    # First try is the default location
    path = "/var/lib/docker/containers/%s/%s-json.log" % (long_id, long_id)
    if os.path.isfile(path):
        return path
    try:
        # Second try is to get docker inspect LogPath
        proc = subprocess.Popen(
               "docker inspect --format '{{.LogPath}}' %s" % long_id,
                shell=True, stdout=subprocess.PIPE)
        path = proc.stdout.read().strip()
        if path != "<no value>" and os.path.isfile(path):
            return path
        # Third try is to use the HostnamePath
        proc = subprocess.Popen(
               "docker inspect --format '{{.HostnamePath}}' %s" % long_id,
                shell=True, stdout=subprocess.PIPE)
        path = proc.stdout.read().strip()
        if path == "<no value>":
            raise IOError("Container %s does not have a docker inspect "
                          ".HostnamePath" % long_id)
        path = os.path.join(os.path.dirname(path), "%s-json.log" % long_id)
        if os.path.isfile(path):
            return path
    except Exception, e:
        raise


"""
We need to keep state about the currently linked container logs,
so whenever one dies (i.e. dead_containers), we can clean his log links.
"""
container_log_links_cache = dict()

def do_link_container_log_files(container_list, env='cloudsight', options=DEFAULT_CRAWL_OPTIONS):
    global container_log_links_cache

    ftype = "logcrawler"
    fopts = options.get(ftype, DEFAULT_CRAWL_OPTIONS.get(ftype, None))
    default_log_files = fopts.get("default_log_files", [])
    host_log_basedir = fopts.get("host_log_basedir",
                                 "/var/log/crawler_container_logs/")
    container_logs_list_file = fopts.get("container_logs_list_file",
                                         "/etc/logcrawl-logs.json")

    # Remove dead containers log links
    for c in container_log_links_cache.values():
        if c not in container_list:
            del container_log_links_cache[c.short_id]
	    logger.info("Un-linking log files for container %s." %
                        c.namespace)

            host_log_dir = get_container_logs_dir(c.namespace, c.pid,
                               c.short_id, c.long_id, host_log_basedir, env)
	    try:
                shutil.rmtree("/tmp/" + c.namespace)
	    except Exception, e:
		logger.exception(e)
		pass
            try:
		shutil.move(host_log_dir, "/tmp/" + c.namespace)
	    except Exception, e:
		logger.exception(e)
		pass

    for c in container_list:
        if container_log_links_cache.has_key(c.short_id):
            logger.info("Logs for container %s already linked." % c.short_id)
            #continue

        host_log_dir = get_container_logs_dir(c.namespace, c.pid, c.short_id,
                                              c.long_id, host_log_basedir, env)
        if not host_log_dir:
            logger.warning("Not linking log files for container " + short_id)
            continue

        logger.info("Linking log files for container %s" % c.short_id)

        # create an empty dir for the container logs
        proc = subprocess.Popen("mkdir -p " + host_log_dir,
                                shell=True, stdout=subprocess.PIPE)
        output = proc.stdout.read()

        """
        If a docker container, link the docker log (usually just stdout
        from each container)
        """
        if c.long_id:
            try:
                docker_log_path = get_docker_container_logs_path(c.long_id)
                docker_host_log_path = os.path.join(host_log_dir, "docker.log")
                os.symlink(docker_log_path, docker_host_log_path)
	    except Exception, e:
		logger.exception(e)
                # We can live without having the docker logs linked
		pass

        # Get the path to the container file system in the host
        proc = subprocess.Popen(
            "awk '{if ($2 == \"/\" && $1 != \"rootfs\") print $1}' /proc/" + 
            c.pid + "/mounts | xargs grep /proc/mounts -e | awk '{print $2}'",
            shell=True, stdout=subprocess.PIPE)
        rootfs_path = proc.stdout.read().strip() + "/rootfs"

        # Generate the container_logs_list
        container_logs_list = get_container_log_files(c, rootfs_path,
                                                      container_logs_list_file)
        container_logs_list.extend(default_log_files)

        # Finally, link the log files
        for logfile in container_logs_list:
            src = rootfs_path + logfile
            if not os.path.exists(src):
		logger.debug("Log file %s does not exist, but linking it anyway" %
			     (src))
	    host_log_path = host_log_dir + logfile
	    try:
		# create the same directory structure
		proc = subprocess.Popen("mkdir -p " +
			    os.path.dirname(host_log_path),
			    shell=True, stdout=subprocess.PIPE)
		output = proc.stdout.read()
		logger.debug("Linking container logfile %s -> %s" %
			     (src, host_log_path))
		os.symlink(src, host_log_path)
	    except IOError as exc:
		logger.exception(exc)
		pass
	    except OSError, exc:
                logger.debug("Link already exists: %s -> %s" %
                             (src, host_log_path))
		pass
	    except Exception, e:
		logger.exception(exc)
		raise
	    if not container_log_links_cache.has_key(c.short_id):
		container_log_links_cache[c.short_id] = c


"""
Returns a list of kvm VMs to crawl like this:
[['instance-000001e3', '3.13.0-40-generic_3.13.0-40.69.x86_64', 'ubuntu', 'x86_64'],
 ['instance-000001df', '3.13.0-40-generic_3.13.0-40.69.x86_64', 'ubuntu', 'x86_64']]
"""
def list_libvirt_domains(user_list):
    import libvirt
    # XXX need to filter user_list
    if user_list == 'ALL':
        domainlist = []
        conn = libvirt.open(None)
        for domain in conn.listAllDomains(0):
            # XXX hardcoded for now
            domainlist.append([domain.name(), '3.13.0-40-generic_3.13.0-40.69.x86_64', 'ubuntu', 'x86_64'])
        return domainlist


def get_libvirt_domain_namespace(domain_name, env='cloudsight'):
    if env == 'cloudsight':
        return domain_name
    elif env == 'alchemy':
        from alchemy import get_namespace
        return get_namespace(domain_name, "kvm")
    else:
        logger.error("Unknown environment %s" % (env))
        return None


def get_ctr_namespace(namespace, pid, short_id, long_id,
                      env='cloudsight', options=DEFAULT_CRAWL_OPTIONS):
    ftype = "metadata"
    fopts = options.get(ftype, DEFAULT_CRAWL_OPTIONS.get(ftype, None))
    namespace_map = fopts.get("namespace_map", {})
    if namespace_map.has_key(long_id):
        return namespace_map[long_id]

    if env == 'cloudsight':
        if pid != "1":
            if not short_id:
                namespace += "/" + pid
            else:
                namespace += "/" + short_id
        return namespace
    elif env == 'alchemy':
        if pid == "1":
            logger.info("get_ctr_namespace() returning None for pid=1 as "
                        "we do not want to crawl the host.")
            return None
        if not long_id:
            logger.info("Not crawling container with pid %s because it does"
                        " not seem to be a docker container." % (pid))
            return None
        else:
            from alchemy import get_namespace
            namespace = get_namespace(long_id, "docker")
            logger.info("crawling %s" % (namespace))
            if not namespace:
                logger.info("Container %s does not have alchemy metadata."
                            % (short_id))
            return namespace
    else:
        logger.error("Unknown environment %s" % (env))
        return None


def snapshot_generic(metadata, crawlmode, urls, snapshot_num, maxfeatures,
                     featurelist, options, format, max_emit_retries):

    crawler = Crawler(feature_epoch=metadata['since_timestamp'],
                      crawl_mode=crawlmode)
    output_urls = ['{0}.{1}'.format(u, snapshot_num) if u.startswith('file:') else u for u in urls]

    # This is used by crawl_interface
    crawler.namespace = metadata['namespace']
    metadata['system_type'] = "vm"

    with Emitter(urls=output_urls, url_args=metadata,
                 compress=metadata['compress'], max_features=maxfeatures,
                 format=format, max_emit_retries=max_emit_retries) as emitter:
        snapshot_single_frame(emitter, featurelist, options, crawler)
        emitter.close_file()


def get_errno_msg(libc):
    try:
        import ctypes
        libc.__errno_location.restype = ctypes.POINTER(ctypes.c_int)
        errno = libc.__errno_location().contents.value
        errno_msg = os.strerror(errno)
        return errno_msg
    except Exception, e:
        return "unknown error"


class ProcessContext:
    def __init__(self, host_ns_fds, host_cwd, container_ns_fds, ct_namespaces):
        self.host_ns_fds = host_ns_fds
        self.host_cwd = host_cwd
        self.container_ns_fds = container_ns_fds
        # mnt has to be last as it changes the /proc mountpoint
        self.ct_namespaces = ct_namespaces


def open_process_namespaces(libc, pid, namespace_fd, ct_namespaces):
    for ct_ns in ct_namespaces:
        try:
            # arg 0 means readonly
            namespace_fd[ct_ns] = libc.open("/proc/" + pid + "/ns/" + ct_ns, 0)
            if namespace_fd[ct_ns] == -1:
                errno_msg = get_errno_msg(libc)
                error_msg = ('Opening the %s namespace file failed: %s'
                             % (ct_ns, errno_msg))
                logger.warning(error_msg)
                if ct_ns == "mnt":
                    raise Exception(error_msg)
        except Exception, e:
            error_msg = 'The open() syscall failed with: %s' % (e)
            logger.warning(error_msg)
            if ct_ns == "mnt":
                raise e


def close_process_namespaces(libc, namespace_fd, ct_namespaces):
    for ct_ns in ct_namespaces:
        try:
            # arg 0 means readonly
            libc.close(namespace_fd[ct_ns])
        except Exception, e:
            error_msg = 'The close() syscall failed with: %s' % (e)
            logger.warning(error_msg)


# Returns a ProcessContext object
def attach_to_container(libc, pid, ct_namespaces):
    # Just to be sure log rotation does not happen in the container
    logging.disable(logging.CRITICAL)
    try:
        host_fds = {}
        container_fds = {}
        host_cwd = os.getcwd()
        open_process_namespaces(libc, "self", host_fds, ct_namespaces)
        open_process_namespaces(libc, pid, container_fds, ct_namespaces)
        ctx = ProcessContext(host_fds, host_cwd, container_fds, ct_namespaces)
    except Exception, e:
        logging.disable(logging.NOTSET)
        logger.exception(e)
        raise

    try:
        attach_to_process_namespaces(libc, container_fds, ct_namespaces)
    except Exception, e:
        logging.disable(logging.NOTSET)
        error_msg = ("Could not attach to the pid=%s container mnt namespace. "
                     "Exception: %s" % (pid, e))
        logger.error(error_msg)
        detach_from_container(libc, ctx)
        raise
    return ctx


def detach_from_container(libc, context):
    try:
        attach_to_process_namespaces(libc, context.host_ns_fds,
                                     context.ct_namespaces)
    except Exception, e:
        logging.disable(logging.NOTSET)
        logger.error("Could not move back to the host: %s" % (e))
        raise
    # We are now in host context
    try:
        os.chdir(context.host_cwd)
    except Exception, e:
        logger.error("Could not move to the host cwd: %s" % (e))
        raise
    logging.disable(logging.NOTSET)
    try:
        close_process_namespaces(libc, context.container_ns_fds,
                                 context.ct_namespaces)
        close_process_namespaces(libc, context.host_ns_fds,
                                 context.ct_namespaces)
    except Exception, e:
        logger.warning("Could not close the namespaces: %s" % (e))


def attach_to_process_namespaces(libc, namespace_fd, ct_namespaces):
    for ct_ns in ct_namespaces:
        try:
            r = libc.setns(namespace_fd[ct_ns], 0)
            if r == -1:
                errno_msg = get_errno_msg(libc)
                error_msg = ("Could not attach to the container '%s'"
                             " namespace (fd=%s): '%s'"
                             % (ct_ns, namespace_fd[ct_ns], errno_msg))
                logger.warning(error_msg)
                if ct_ns == "mnt":
                    raise Exception(error_msg)
        except Exception, e:
            error_msg = 'The setns() syscall failed with: %s' % (e)
            logger.warning(error_msg)
            if ct_ns == "mnt":
                logger.exception(e)
                raise e


def new_urls_for_container(urls, short_id, pid, snapshot_num):
    for u in urls:
        if u.startswith('file:'):
            if not short_id:
                file_suffix = '{0}.{1}'.format(pid, snapshot_num)
            else:
                file_suffix = '{0}.{1}'.format(short_id, snapshot_num)
            yield('{0}.{1}'.format(u, file_suffix))
        else:
            yield(u)


def load_libc_for_containers():
    from ctypes import CDLL
    try:
        libc = CDLL('libc.so.6')
    except Exception, e:
        logger.warning('Can not crawl containers as there is no libc: %s' % e)
        raise e
    # Check if there if we can load libc.setns()
    if 'libc' not in locals() or not hasattr(libc, "setns"):
        logger.warning('Can not crawl container. There is no setns: %s' % e)
        raise e
    return libc


def get_filtered_list_of_containers(user_list, process_id, process_count,
                                    host_namespace, environment,
                                    options=DEFAULT_CRAWL_OPTIONS):
    filtered_list = []
    containers_list = list_all_containers(user_list)
    for c in containers_list:
        # This is to crawl a subspace of all the containers
        _hash = c.long_id if c.long_id else c.short_id
        num = int(_hash, 16) % int(process_count)
        if num == process_id:
            namespace = get_ctr_namespace(host_namespace, c.pid, c.short_id,
                                          c.long_id, environment, options)
            if namespace:
                filtered_list.append(Container(c.pid, c.short_id, c.long_id,
                                               c.name, c.image, namespace))
    return filtered_list


def snapshot_all_containers(metadata, crawlmode, urls, snapshot_num,
                            maxfeatures, featurelist, options, format,
                            user_list, environment, max_emit_retries,
                            process_id, process_count, link_container_log_files):

    # Quickly check if we can actually crawl containers
    libc = load_libc_for_containers()

    host_namespace = metadata['namespace']
    filtered_list = get_filtered_list_of_containers(user_list, process_id,
                        process_count, host_namespace, environment, options)

    logger.info("Process %d (out of %d) crawling %d containers" %
                (process_id, process_count, len(filtered_list)))

    # Link the container log files into a known location in the host
    if link_container_log_files:
        do_link_container_log_files(filtered_list, environment, options)

    # For all containers that were not filtered out
    for c in filtered_list:
        logger.debug("Trying to crawl container %s %s %s" %
                     (c.pid, c.short_id, c.namespace))
        crawler = Crawler(feature_epoch=metadata['since_timestamp'],
                          crawl_mode=crawlmode, container_long_id=c.long_id,
                          namespace=c.namespace)

        metadata['namespace'] = c.namespace
        metadata['system_type'] = "container"
        metadata['container_long_id'] = c.long_id
        # XXX this '/' is because of issue #342
        metadata['container_name'] = c.name[1:] if c.name[0] == '/' else c.name
        metadata['container_image'] = c.image
        output_urls = new_urls_for_container(urls, c.short_id, c.pid, snapshot_num)

        with Emitter(urls=output_urls, url_args=metadata,
                     compress=metadata['compress'], max_features=maxfeatures,
                     format=format, max_emit_retries=max_emit_retries) as emitter:

            snapshot_linux_container(emitter, featurelist, options, crawler,
                                     c.pid, c.short_id, c.long_id, libc,
                                     c.namespace)


# Function for the container_crawler process
def container_crawler_func(emitter, featurelist, options, crawler, queue):
    try:
        snapshot_single_frame(emitter, featurelist, options, crawler)
    except Exception, e:
        emitter.close_file()
        sys.exit(1)
    try:
        queue.put(crawler.get_temp_changes(), block=True, timeout=1)
    except Exception, e:
        pass
    queue.close()
    emitter.close_file()
    sys.exit(0)


def snapshot_linux_container(emitter, featurelist, options, crawler,
                             pid, short_id, long_id, libc,
                             ctr_namespace):
    global child_process

    '''
    These metrics are obtained using cgroups and we specifically use
    docker cgroups. So, we can continue with these only if they are 
    docker containers, that is, if they have long_id (docker IDs).
    '''
    out_features = ['cpu', 'memory', 'dockerhistory',
                    'dockerps', 'dockerinspect']

    '''
    We will crawl everything except cpu and memory which should
    be crawled from the host (cgroup metadata) and not the container.
    '''
    if long_id:
        # XXX right now we only support docker containers for these features
        features = [feat for feat in featurelist if feat in out_features]
        prev_crawlmode = crawler.crawl_mode
        crawler.crawl_mode = 'OUTCONTAINER'
        snapshot_single_frame(emitter, features, options, crawler)
        crawler.crawl_mode = prev_crawlmode

    """
    Continue with the next container if this one died, or if there
    are no in container features to crawl.
    """
    features = [feat for feat in featurelist if feat not in out_features]
    if not os.path.exists("/proc/" + pid) or not features:
        return

    logger.info("Moving to container %s (pid=%s)" % (short_id, pid))

    """
    We are moving "inside" the container, so we change the mode to INVM.
    """
    crawler.crawl_mode = 'INVM'

    try:
        # For the interface feature, just need to attach to the net namespace
        if features == ['interface']:
            ct_namespaces = ["net"]
        else:
            ct_namespaces = ["user", "pid", "uts", "ipc", "net", "mnt"]
        context = attach_to_container(libc, pid, ct_namespaces)
    except Exception, e:
        logger.debug("Could not attach to container %s" % (short_id))
        raise

    """
    If we don't flush the file buffer, when we fork for the container
    we will end up with this buffer data being written twice to the file.
    """
    emitter.flush_file()

    """
    The crawler keeps a cache of measurements. This queue stores the changes.
    """
    queue = multiprocessing.Queue()

    child_process = multiprocessing.Process(name="crawler-%s" % (pid),
                            target=container_crawler_func,
                            args=(emitter, features, options, crawler, queue))
    child_process.start()

    child_process.join(60)
    if child_process.is_alive():
        errmsg = "Timed out waiting for process %d" % (child_process.pid)
        queue.close()
        os.kill(child_process.pid, 9)
        logging.disable(logging.NOTSET)
        logger.error(errmsg)
        raise RuntimeError(errmsg)

    changes = queue.get()
    crawler.cache_apply_changes(changes)

    logger.debug("Done with container %s (pid=%s)" % (short_id, pid))

    try:
        detach_from_container(libc, context)
    except Exception, e:
        logger.error("Could not detach from container %s." % (short_id))
        raise


# Only linux KVM-qemu supported
def snapshot_libvirt_domain(metadata, crawlmode, urls, snapshot_num,
                            maxfeatures, featurelist, options, format,
                            libvirt_domains_list, environment, max_emit_retries):
    # namespace will be over-written for each VM
    namespace = metadata['namespace']
    metadata['system_type'] = "vm"

    # Cumulative number of crawled features for all VMs
    global_num_features = 0

    for vm in list_libvirt_domains(libvirt_domains_list):
        domain_name, kernel_version, distro, arch = vm

        logger.info('Trying to crawl VM domain=%s' % (domain_name))

        crawler = Crawler(feature_epoch=metadata['since_timestamp'],
                          crawl_mode=crawlmode, vm=vm)
        domain_namespace = get_libvirt_domain_namespace(domain_name, environment)

        # if could not determine namespace then do not crawl it
        if not domain_namespace:
            logger.info('Can not crawl VM domain=%s' % (domain_name))
            continue

        logger.info('Using namespace %s for domain=%s' %
                    (domain_namespace, domain_name))

        """
        For VMs, the namespace is the domain_namespace. Containers' namespaces
        on the other hand are hierarchical: "hostname/containername".
        """
        metadata['namespace'] = domain_namespace

        output_urls = ['{0}.{1}.{2}'.format(u, domain_namespace, snapshot_num) if u.startswith('file:') else u for u in urls]
        emitter = Emitter(urls=output_urls, url_args=metadata,
             compress=metadata['compress'], max_features=maxfeatures,
             format=format, max_emit_retries=max_emit_retries)
        emitter.__enter__()

        # Each VM emitter stores all the crawled features in global_num_features
        emitter.global_num_features = global_num_features
        snapshot_single_frame(emitter, featurelist, options, crawler)
        emitter.close_file()
        emitter.__exit__(None, None, None)

"""
The main job of this handler is to kill all the children.
"""
child_process = None
def signal_handler(signum, stack):
    global child_process
    try:
        logger.error("Killing %s" % (child_process))
        os.kill(child_process.pid, 9)
    except Exception, e:
        pass
    sys.exit(1)


"""
This is a very interesting hack. The problem with not loading every
module we need before moving to a container is that those modules might
not be present in the container file system. Some python modules need
to actually be used in order to be loaded.
"""
def hack_to_pre_load_modules():
    queue = multiprocessing.Queue()
    def foo(queue):
        queue.put("dummy")
        pass
    p = multiprocessing.Process(target=foo, args=(queue,))
    p.start()
    p.join()
    queue.get()


def check_pid(pid):        
    """ Check For the existence of a unix pid. """
    if not pid:
        return True
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


def snapshot(urls=['file://frame'], namespace=get_host_ipaddr(),
             features=DEFAULT_FEATURES_TO_CRAWL,
             options=DEFAULT_CRAWL_OPTIONS, maxfeatures=sys.maxint,
             since='BOOT', frequency=-1, compress=True, crawlmode='INVM',
             mountpoint='Undefined', inputfile='Undefined', format='csv',
             docker_containers_list=None, libvirt_domains_list=None,
             environment='cloudsight', max_emit_retries=5, process_id=0,
             process_count=1, parent_pid=None, extra_metadata=None,
             extra_metadata_for_all=False, link_container_log_files=False):

    '''
    Modify options to make sure we are pointing to the right mountpoints
    for various features.
    '''
    if crawlmode == 'MOUNTPOINT':
        options['os']['mountpoint'] = mountpoint
        options['package']['root_dir'] = mountpoint
        options['file']['root_dir'] = mountpoint
        options['file']['root_dir_alias'] = '/' #To remove /mnt/CrawlDisk from each reported file path
        options['config']['root_dir'] = mountpoint
        options['config']['root_dir_alias'] = '/' #To remove /mnt/CrawlDisk from each reported config file path
    logger.debug('Snapshot: url={0}, namespace={1}, features={2}, options={3}, since={4}, frequency={5}, compress={6}, crawlmode={7}'.format(
                                        urls, namespace, features, json.dumps(options), since, frequency, compress, crawlmode))
    if crawlmode == 'MOUNTPOINT':
        logger.debug('Snapshot: mountpoint={0}'.format(mountpoint))
    if crawlmode == 'FILE':
        logger.debug('Snapshot: input frame file={0}'.format(inputfile))
    if crawlmode == 'OUTVM':
        logger.debug('Snapshot: Libvirt domains={0}'.format(libvirt_domains_list))
    if maxfeatures < sys.maxint:
        logger.debug('Snapshot: will emit at most %d features' % maxfeatures)
    
    if crawlmode != 'INVM' and since != 'EPOCH':
        logger.error('Only --since EPOCH is supported in out of VM crawler. Using --since EPOCH')
        since = 'EPOCH'   
    last_snapshot_time = (psutil.boot_time() if hasattr(psutil, "boot_time")
                          else psutil.BOOT_TIME)
    if since == 'EPOCH':
        since_timestamp = 0
    elif since == 'BOOT':
        since_timestamp = (psutil.boot_time() if hasattr(psutil, "boot_time")
                           else psutil.BOOT_TIME)
    elif since == 'LASTSNAPSHOT':
        since_timestamp = last_snapshot_time # subsequent snapshots will update this value
    else:
        # check if the value of since is a UTC timestamp (integer)
        try:
            since_timestamp = int(since)
        except:
            logger.error('Invalid value since={0}, defaulting to BOOT'.format(since))
            since = 'BOOT'
            since_timestamp = last_snapshot_time # subsequent snapshots will update this value
    log_atime_config(path=options['file']['root_dir'],crawlmode=crawlmode)

    featurelist = features.split(',')
    snapshot_num = 0

    if crawlmode == 'OUTCONTAINER':
        hack_to_pre_load_modules()
        import signal
        signal.signal(signal.SIGTERM, signal_handler)

    while True:
        logger.debug('snapshot #{0}'.format(snapshot_num))

        snapshot_time = int(time.time())
        metadata = {
            'namespace': namespace,
            'features' : features,
            'timestamp': snapshot_time,
            'since': since,
            'since_timestamp': since_timestamp,
            'compress': compress,
            'extra': extra_metadata,
            'extra_all_features': extra_metadata_for_all
        }

        if crawlmode == 'OUTCONTAINER':
            # Containers (not limited to docker containers)
            snapshot_all_containers(metadata=metadata, crawlmode=crawlmode,
                urls=urls, snapshot_num=snapshot_num, maxfeatures=maxfeatures,
                featurelist=featurelist, options=options, format=format,
                user_list=docker_containers_list,
                environment=environment, max_emit_retries=max_emit_retries,
                process_id=process_id, process_count=process_count,
                link_container_log_files=link_container_log_files)
        elif crawlmode == 'OUTVM':
            # KVM
            snapshot_libvirt_domain(metadata=metadata, crawlmode=crawlmode,
                urls=urls, snapshot_num=snapshot_num, maxfeatures=maxfeatures,
                featurelist=featurelist, options=options, format=format,
                libvirt_domains_list=libvirt_domains_list,
                environment=environment, max_emit_retries=max_emit_retries)
        else:
            snapshot_generic(metadata=metadata, crawlmode=crawlmode,
                urls=urls, snapshot_num=snapshot_num, maxfeatures=maxfeatures,
                featurelist=featurelist, options=options, format=format,
                max_emit_retries=max_emit_retries)

        # check the parent
        if not check_pid(parent_pid):
            logger.info("Main process with pid %d died, so exiting." % parent_pid)
            raise Exception("Main process %d died." % (parent_pid))

        if frequency <= 0:
            break
        else:
            if since == 'LASTSNAPSHOT':
                since_timestamp = snapshot_time # subsequent snapshots will update this value
            time.sleep(frequency)
            snapshot_num += 1


## for unit testing only
if __name__ == '__main__':

    logging.basicConfig(filename='crawler.log', filemode='w', format='%(asctime)s %(levelname)s : %(message)s', level=logging.DEBUG)
    # create a snapshot to a local file

    framefile = '/tmp/testframe.csv'
    print 'Emitting snapshot to local file'
    namespace = "server1"
    snapshot(urls=['file://{0}'.format(framefile)], namespace=namespace,
             features='cpu,interface,dockerps,dockerhistory,dockerinspect',
             since='BOOT', compress=False, docker_containers_list="29ae9b4daa0b",
             crawlmode='OUTCONTAINER',
             format="csv", environment="cloudsight")
    # Sanity check the output frame by reading it back in
    print 'Reading features from local snapshot file'
    Feature = namedtuple('Feature', ['type', 'resource', 'value'])
    with open(framefile + ".1.0", 'r') as fd:
        csv.field_size_limit(sys.maxsize) # to handle large values
        csv_reader = csv.reader(fd, delimiter='\t', quotechar="'")
        num_features = 0
        for row in csv_reader:
            feature = Feature(row[0], json.loads(row[1]), json.loads(row[2]))
            # print feature.type, feature.resource, feature.value
            num_features += 1
        print 'Successfully read %d features' % num_features
