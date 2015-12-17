#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
from container import Container
import subprocess


class DockerContainer(Container):

    def __init__(
        self,
        pid,
        long_id,
        short_id=None,
        names=[],
        image=None,
        namespace=None,
        running='Unknown',
        created=None,
        network_settings=None,
        cmd=None,
    ):

        self.pid = pid
        self.long_id = long_id
        if long_id and not short_id:
            self.short_id = long_id[:12]
        else:
            self.short_id = short_id

        # XXX what about multiple names?

        self.names = names
        self.name = names
        self.image = image
        self.namespace = namespace
        self.running = running
        self.created = created
        self.network_settings = network_settings
        self.cmd = cmd

        # For some reason docker prepends a '/' to the name.
        if self.name[0] == '/':
            self.name = self.name[1:]

    @classmethod
    def fromInspect(container, inspect):
        state = inspect['State']
        image = inspect['Image']

        # Docker inspect sometimes returns the pid in scientific notation

        pid = '%.0f' % float(state['Pid'])
        return container(
            long_id=inspect['Id'],
            pid=pid,
            image=image,
            names=inspect['Name'],
            running=state['Running'],
            created=inspect['Created'],
            network_settings=inspect['NetworkSettings'],
            cmd=inspect['Config']['Cmd'],
        )

    def linkLogFiles(self):
        pass

    def isDockerContainer(self):
        return True

    # Find the mount point of the specified cgroup

    def get_cgroup_dir(self, dev=''):
        paths = [os.path.join('/cgroup/', dev),
                 os.path.join('/sys/fs/cgroup/', dev)]
        for path in paths:
            if os.path.ismount(path):
                return path

        # Try getting the mount point from /proc/mounts

        try:
            proc = subprocess.Popen(
                'grep "cgroup/' +
                dev +
                ' " /proc/mounts | awk \'{print $2}\'',
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            return proc.stdout.read().strip()
        except Exception as e:
            raise e

    def getMemoryCgroupPath(self, node='memory.stat'):
        return os.path.join(self.get_cgroup_dir('memory'), 'docker',
                            self.long_id, node)

    def getCpuCgroupPath(self, node='cpuacct.usage'):
        return os.path.join(self.get_cgroup_dir('cpuacct'), 'docker',
                            self.long_id, node)

    def __str__(self):
        return str(self.__dict__)
