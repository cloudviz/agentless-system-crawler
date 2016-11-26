#!/usr/bin/python
# -*- coding: utf-8 -*-

DEFAULT_ENVIRONMENT = 'cloudsight'
DEFAULT_PLUGIN_PLACES = 'plugins'
DEFAULT_COMPRESS = False
DEFAULT_PARTITION_STRATEGY = {'name': 'equally_by_pid',
                              'args': {'process_id': 0,
                                       'num_processes': 1}}
DEFAULT_METADATA = {'container_long_id_to_namespace_map': {},
                    'extra_metadata': {},
                    'extra_metadata_for_all': False}
DEFAULT_LINK_CONTAINER_LOG_FILES = False
DEFAULT_MOUNTPOINT = 'Undefined'
DEFAULT_DOCKER_CONTAINERS_LIST = 'ALL'
DEFAULT_AVOID_SETNS = False

DEFAULT_CRAWL_OPTIONS = {
    'os': {'avoid_setns': DEFAULT_AVOID_SETNS},
    'disk': {},
    'package': {'avoid_setns': DEFAULT_AVOID_SETNS},
    'process': {},
    'metric': {},
    'connection': {},
    'mesos_url': 'http://localhost:9092',
    'file': {'root_dir': '/', 'avoid_setns': DEFAULT_AVOID_SETNS,
             'exclude_dirs': [
                 'boot',
                 'dev',
                 'proc',
                 'sys',
                 'mnt',
                 'tmp',
                 'var/cache',
                 'usr/share/man',
                 'usr/share/doc',
                 'usr/share/mime',
             ]},
    'config': {'avoid_setns': DEFAULT_AVOID_SETNS,
               'root_dir': '/',
               'exclude_dirs': [
                   'dev',
                   'proc',
                   'mnt',
                   'tmp',
                   'var/cache',
                   'usr/share/man',
                   'usr/share/doc',
                   'usr/share/mime',
               ],
               'known_config_files': [
                   'etc/passwd',
                   'etc/group',
                   'etc/hosts',
                   'etc/hostname',
                   'etc/mtab',
                   'etc/fstab',
                   'etc/aliases',
                   'etc/ssh/ssh_config',
                   'etc/ssh/sshd_config',
                   'etc/sudoers',
               ],
               'discover_config_files': True,
               },
    'memory': {},
    'interface': {},
    'cpu': {},
    'load': {},
    'gpu': {},
    'dockerps': {},
    'dockerhistory': {},
    'dockerinspect': {},
    '_test_crash': {},
    '_test_infinite_loop': {},
    'logcrawler': {
        'host_log_basedir': '/var/log/crawler_container_logs/',
        'log_types_file': 'd464347c-3b99-11e5-b0e9-062dcffc249f.type-mapping',
        'default_log_files': [{'name': '/var/log/messages',
                               'type': None},
                              {'name': '/etc/csf_env.properties',
                               'type': None},
                              ],
    },
    'metadata': DEFAULT_METADATA,
    'partition_strategy': DEFAULT_PARTITION_STRATEGY,
    'environment': DEFAULT_ENVIRONMENT,
    'compress': DEFAULT_COMPRESS,
    'link_container_log_files': DEFAULT_LINK_CONTAINER_LOG_FILES,
    'mountpoint': DEFAULT_MOUNTPOINT,
    'docker_containers_list': DEFAULT_DOCKER_CONTAINERS_LIST
}

DEFAULT_FEATURES_TO_CRAWL = 'os,cpu'
