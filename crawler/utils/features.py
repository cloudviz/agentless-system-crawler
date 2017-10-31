#!/usr/bin/python
# -*- coding: utf-8 -*-
from collections import namedtuple

OSFeature = namedtuple('OSFeature', [
    'boottime',
    'uptime',
    'ipaddr',
    'os',
    'os_version',
    'os_kernel',
    'architecture',
])
FileFeature = namedtuple('FileFeature', [
    'atime',
    'ctime',
    'gid',
    'linksto',
    'mode',
    'mtime',
    'name',
    'path',
    'size',
    'type',
    'uid',
])
ConfigFeature = namedtuple('ConfigFeature', ['name', 'content', 'path'])
DiskFeature = namedtuple('DiskFeature', [
    'partitionname',
    'freepct',
    'fstype',
    'mountpt',
    'mountopts',
    'partitionsize',
])
DiskioFeature = namedtuple('DiskioFeature', [
    'readoprate',
    'writeoprate',
    'readbytesrate',
    'writebytesrate',
])
ProcessFeature = namedtuple('ProcessFeature', [
    'cmd',
    'created',
    'cwd',
    'pname',
    'openfiles',
    'mmapfiles',
    'pid',
    'ppid',
    'threads',
    'user',
])
MetricFeature = namedtuple('MetricFeature', [
    'cpupct',
    'mempct',
    'pname',
    'pid',
    'read',
    'rss',
    'status',
    'user',
    'vms',
    'write',
])
ConnectionFeature = namedtuple('ConnectionFeature', [
    'localipaddr',
    'localport',
    'pname',
    'pid',
    'remoteipaddr',
    'remoteport',
    'connstatus',
])
PackageFeature = namedtuple('PackageFeature', ['installed', 'pkgname',
                                               'pkgsize', 'pkgversion',
                                               'pkgarchitecture'])
MemoryFeature = namedtuple('MemoryFeature', [
    'memory_used',
    'memory_buffered',
    'memory_cached',
    'memory_free',
    'memory_util_percentage'
])
CpuFeature = namedtuple('CpuFeature', [
    'cpu_idle',
    'cpu_nice',
    'cpu_user',
    'cpu_wait',
    'cpu_system',
    'cpu_interrupt',
    'cpu_steal',
    'cpu_util',
])
InterfaceFeature = namedtuple('InterfaceFeature', [
    'if_octets_tx',
    'if_octets_rx',
    'if_packets_tx',
    'if_packets_rx',
    'if_errors_tx',
    'if_errors_rx',
])
LoadFeature = namedtuple('LoadFeature', ['shortterm', 'midterm',
                                         'longterm'])
DockerPSFeature = namedtuple('DockerPSFeature', [
    'Status',
    'Created',
    'Image',
    'Ports',
    'Command',
    'Names',
    'Id',
])
DockerHistoryFeature = namedtuple('DockerHistoryFeature', ['history'])
ModuleFeature = namedtuple('ModuleFeature', ['name', 'state'])
CpuHwFeature = namedtuple('CpuHwFeature', [
    'cpu_family',
    'cpu_vendor',
    'cpu_model',
    'cpu_vedor_id',
    'cpu_module_id',
    'cpu_khz',
    'cpu_cache_size_kb',
    'cpu_num_cores'])
JarFeature = namedtuple('JarFeature', [
    'name',
    'path',
    'jarhash',
    'hashes',
])
