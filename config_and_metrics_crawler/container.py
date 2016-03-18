#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import logging
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
        container_opts={},
    ):
        self.pid = str(pid)
        self.short_id = str(hash(pid))
        self.long_id = str(hash(pid))
        self.name = str(pid)
        self.namespace = None
        self.image = None
        self.root_fs = None
        self.runtime_env = None
        self.log_prefix = None
        self.log_file_list = None

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

    def setup_namespace_and_metadata(self, container_opts={}):
        environment = container_opts.get('environment', 'cloudsight')
        runtime_env = None
        try:
            if environment == 'cloudsight':
                import cloudsight as runtime_env
            elif environment == 'watson':
                import watson as runtime_env
            elif environment == 'alchemy':
                import alchemy as runtime_env
            else:
                raise ContainerInvalidEnvironment(
                    'Unknown environment %s' % environment)
            self.runtime_env = runtime_env
        except ImportError:
            raise ImportError('Please setup {}.py correctly.'.format(environment))

        _map = container_opts.get('long_id_to_namespace_map', {})
        if self.long_id in _map:
            return _map[self.long_id]

        host_namespace = container_opts.get('host_namespace', 'undefined')
        environment = container_opts.get('environment', 'cloudsight')
        container_logs = container_opts.get('container_logs');
        self.root_fs = get_docker_container_rootfs_path(self.long_id)

        if not self.is_docker_container():
            raise AlchemyInvalidContainer()

        try:
            _options = {'root_fs': self.root_fs, 'type': 'docker',
                'name': self.name, 'host_namespace': host_namespace,
                'container_logs': container_logs}
            namespace = self.runtime_env.get_namespace(self.long_id, _options)
            if not namespace:
                logger.warning('Container %s does not have alchemy '
                           'metadata.' % self.short_id)
                raise AlchemyInvalidMetadata()
            self.namespace = namespace

            self.log_prefix = self.runtime_env.get_container_log_prefix(
                            self.long_id, _options)

            self.log_file_list = self.runtime_env.get_log_file_list(
                            self.long_id, _options)
        except ValueError:
            logger.warning('Container %s does not have a valid alchemy '
                           'metadata json file.' % self.short_id)
            raise AlchemyInvalidMetadata()

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
