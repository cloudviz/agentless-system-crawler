#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import logging

try:
    import alchemy
except ImportError:
    alchemy = None

import defaults
from crawler_exceptions import (
    ContainerInvalidEnvironment,
    AlchemyInvalidMetadata,
    AlchemyInvalidContainer)


from dockerutils import get_docker_container_rootfs_path

logger = logging.getLogger('crawlutils')


class Container(object):
    """
    This class abstracts a running Linux container.

    A running container is defined as a process subtree with the `pid`
    namespace different to the `init` process `pid` namespace.
    """

    def __init__(
        self,
        pid,
        namespace_opts={},
    ):
        self.pid = str(pid)
        self.short_id = str(hash(pid))
        self.long_id = str(hash(pid))
        self.name = str(pid)
        self.namespace = None
        self.image = None

    def __eq__(self, other):
        """
        A container is equal to another if they have the same PID
        """
        return self.pid == other.pid

    def __ne__(self, other):
        return not self.__eq__(other)

    def is_docker_container(self):
        return False

    def __str__(self):
        return str(self.__dict__)

    def setup_namespace_and_metadata(self, namespace_opts={}):
        self.namespace = self._get_namespace(namespace_opts)

    def _get_namespace(self, namespace_opts={}):

        _map = namespace_opts.get('long_id_to_namespace_map', {})
        if self.long_id in _map:
            return _map[self.long_id]

        host_namespace = namespace_opts.get('host_namespace', 'undefined')
        environment = namespace_opts.get('environment', 'cloudsight')
        namespace = None

        if environment == 'cloudsight':
            name = (self.name if len(self.name) > 0 else self.short_id)
            name = (name[1:] if name[0] == '/' else name)
            namespace = host_namespace + '/' + name
        elif environment == 'alchemy':
            if not self.is_docker_container():
                raise AlchemyInvalidContainer()

            if alchemy is None:
                raise ImportError('Please setup alchemy.py correctly.')

            try:
                namespace = alchemy.get_namespace(self.long_id, 'docker')
            except ValueError:
                logger.warning('Container %s does not have a valid alchemy '
                               'metadata json file.' % self.short_id)
                raise AlchemyInvalidMetadata()
            if not namespace:
                logger.warning('Container %s does not have alchemy '
                               'metadata.' % self.short_id)
                raise AlchemyInvalidMetadata()
        elif environment == 'watson':
            prefix_key = namespace_opts.get('containerNamespace','CRAWLER_METRIC_PREFIX')
            config_file = namespace_opts.get('watsonPropertiesFile','/etc/csf_env.properties')
            if config_file[0] == '/': config_file = config_file[1:]
            rootfs = get_docker_container_rootfs_path(self.long_id)
            namespace = None
            if rootfs:
                with open(os.path.join(rootfs,config_file),'r') as rp:
                    lines = dict([l.strip().split('=') for l in rp.readlines()])
                    namespace = ".".join([lines[p[1:]].strip('\'') for p in lines.get(prefix_key,"").split(':')])
                    namespace += '.' + self.short_id
        else:
            raise ContainerInvalidEnvironment(
                'Unknown environment %s' % environment)
        return namespace

    # Find the mount point of the specified cgroup

    def get_cgroup_dir(self, dev=''):
        raise NotImplementedError()

    def get_memory_cgroup_path(self, node='memory.stat'):
        raise NotImplementedError()

    def get_cpu_cgroup_path(self, node='cpuacct.usage'):
        raise NotImplementedError()

    def is_running(self):
        return os.path.exists('/proc/' + self.pid)

    def link_logfiles(self,
                      options=defaults.DEFAULT_CRAWL_OPTIONS):
        pass

    def unlink_logfiles(self,
                        options=defaults.DEFAULT_CRAWL_OPTIONS):
        pass
