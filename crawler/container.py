#!/usr/bin/python
# -*- coding: utf-8 -*-
import os


class Container(object):

    def __init__(
        self,
        pid,
        short_id=None,
        long_id=None,
        name=None,
        image=None,
        namespace=None,
    ):
        self.pid = str(pid)
        self.namespace = namespace
        if short_id:
            self.short_id = short_id
        else:
            self.short_id = str(hash(pid))
        if long_id:
            self.long_id = long_id
        else:
            self.long_id = short_id
        self.name = str(pid)
        self.image = image

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.__dict__ \
            == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)

    def linkLogFiles(self):
        pass

    def isDockerContainer(self):
        return False

    def __str__(self):
        return str(self.__dict__)

    # Find the mount point of the specified cgroup

    def get_cgroup_dir(self, dev=''):
        pass

    def getMemoryCgroupPath(self, node='memory.stat'):
        pass

    def isRunning(self):
        return os.path.exists('/proc/' + self.pid)
