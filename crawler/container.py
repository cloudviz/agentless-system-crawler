#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import logging
import defaults
from crawler_exceptions import (
    ContainerInvalidEnvironment,
    AlchemyInvalidMetadata,
    AlchemyInvalidContainer)

# XXX-kollerr anything docker specific should go to dockercontainer.py
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
        logger.info('setup_namespace_and_metadata: long_id=' +
                       self.long_id)
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

        host_namespace = namespace_opts.get('host_namespace', 'undefined')
        environment = namespace_opts.get('environment', 'cloudsight')
        namespace = None

        if environment == 'cloudsight':
            name = self.name or self.short_id
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
                # XXX-kollerr this should not be alchemy specific either
                raise AlchemyInvalidMetadata()
            self.namespace = namespace

            self.log_prefix = self.runtime_env.get_container_log_prefix(
                            self.long_id, _options)

            self.log_file_list = self.runtime_env.get_log_file_list(
                            self.long_id, _options)
        except ValueError:
            # XXX-kollerr this ValueError looks suspiciously very specific
            # to alchemy. Are you sure watson.py will be throwing ValueError?
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
