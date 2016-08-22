#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import logging
import defaults

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
        self.namespace = str(pid)
        self.image = None
        self.root_fs = None
        self.log_prefix = None
        self.log_file_list = None

        # XXX(kollerr): when running in alchemy environment, non-alchemy
        # containres should be ignored

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

    def get_memory_cgroup_path(self, node='memory.stat'):
        raise NotImplementedError()

    def get_cpu_cgroup_path(self, node='cpuacct.usage'):
        raise NotImplementedError()

    def is_running(self):
        return os.path.exists('/proc/' + self.pid)

    def link_logfiles(self,
                      options=defaults.DEFAULT_CRAWL_OPTIONS):
        raise NotImplementedError()

    def unlink_logfiles(self,
                        options=defaults.DEFAULT_CRAWL_OPTIONS):
        raise NotImplementedError()
