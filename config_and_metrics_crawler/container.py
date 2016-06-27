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
            self.namespace = _map[self.long_id]
	    # XXX assert that there are no logs being linked as that won't be
	    # supported now
            return

        host_namespace = container_opts.get('host_namespace', 'undefined')
        environment = container_opts.get('environment', 'cloudsight')
        container_logs = container_opts.get('container_logs');

        # XXX-kollerr only alchemy and watson containers are meant to be docker
        # this check is wrong. This should only apply to watson and alchemy.
        #
        # Just in case, a linux container is any process running in a different
        # namespace than the host root namespace. So, there are other containers
        # running in teh system besides docker containers.
        if not self.is_docker_container():
            # XXX-kollerr So if we are only doing Docker container stuff below,
            # everything below here should be in dockercontainer.py
            raise AlchemyInvalidContainer()

        if environment == 'watson':
	    # XXX-kollerr only docker containers have a rootfs. This code is
	    # supposed to be docker agnostic. Moreover, this really applies to
	    # watson containers only.
            self.root_fs = get_docker_container_rootfs_path(self.long_id)
        else:
            self.root_fs = None

        try:
            _options = {'root_fs': self.root_fs, 'type': 'docker',
                'name': self.name, 'host_namespace': host_namespace,
                'container_logs': container_logs}
            namespace = self.runtime_env.get_namespace(self.long_id, _options)
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