#!/usr/bin/python
# -*- coding: utf-8 -*-
from collections import namedtuple

OSFeature = namedtuple('OSFeature', [
    'boottime',
    'uptime',
    'ipaddr',
    'osdistro',
    'osname',
    'osplatform',
    'osrelease',
    'ostype',
    'osversion',
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
ProcessFeature = namedtuple('ProcessFeature', [
    'cmd',
    'created',
    'cwd',
    'pname',
    'openfiles',
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
