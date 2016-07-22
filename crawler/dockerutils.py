#!usr/bin/python
# -*- coding: utf-8 -*-
import os
import logging
import subprocess
import dateutil.parser as dp
import semantic_version
import docker

# version at which docker image layer organization changed
VERSION_SPEC = semantic_version.Spec('>=1.10.0')

logger = logging.getLogger('crawlutils')

from crawler_exceptions import (DockerutilsNoJsonLog,
                                DockerutilsException)


def exec_dockerps():
    """
    Returns a list of docker inspect jsons, one for each container.

    This call executes the `docker inspect` command every time it is invoked.
    """
    client = docker.Client(
        base_url='unix://var/run/docker.sock', version='auto')
    containers = client.containers()
    inspect_arr = []
    for container in containers:
        inspect = exec_dockerinspect(container['Id'])
        inspect_arr.append(inspect)

    return inspect_arr


def exec_docker_history(long_id=None):
    client = docker.Client(
        base_url='unix://var/run/docker.sock', version='auto')
    containers = client.containers()
    out = None
    for c in containers:
        if long_id == c['Id']:
            image = c['Image']
            # If there is no tag present on the image name, this is implicitly "latest"
            # Docker defaults to this
            out = client.history(image)
    del client
    return out


def _fold_port_key(ports_dict):
    if not ports_dict:
        return None

    # map network settings in ports
    pd = []
    for (k, v) in ports_dict.iteritems():
        (port, proto) = ((k, '') if '/' not in k else k.split('/'))
        if v:
            for i in v:
                i['Protocol'] = proto
        else:
            v = [{'HostPort': port, 'HostIp': '',
                  'Protocol': proto}]
        pd.append(v)
    return pd


def _reformat_inspect(inspect):
    """Fixes some basic issues with the inspect json returned by docker.
    """
    # For some reason, Docker inspect sometimes returns the pid in scientific
    # notation.
    inspect['State']['Pid'] = '%.0f' % float(inspect['State']['Pid'])

    np = _fold_port_key(inspect['NetworkSettings']['Ports'])
    if np:
        inspect['NetworkSettings']['Ports'] = np

    np = _fold_port_key(inspect['HostConfig']['PortBindings'])
    if np:
        inspect['HostConfig']['PortBindings'] = np

    docker_datetime = dp.parse(inspect['Created'])
    epoch_seconds = docker_datetime.strftime('%s')
    inspect['Created'] = epoch_seconds


def exec_dockerinspect(long_id=None):
    client = docker.Client(
        base_url='unix://var/run/docker.sock', version='auto')

    if not long_id:
        containers = client.containers()
        if len(containers) < 1:
            return None
        long_id = client.containers[0]['Id']

    inspect = client.inspect_container(long_id)
    _reformat_inspect(inspect)

    try:
        # get the first RepoTag
        inspect['RepoTag'] = client.inspect_image(inspect['Image'])['RepoTags'][0]
    except (KeyError, IndexError):
        inspect['RepoTag'] = ''

    return inspect


def get_docker_storage_driver():
    """
    We will try several steps in order to ensure that we return
    one of the 3 types (btrfs, devicemapper, aufs).
    """
    driver = None

    # Step 1.a, get it from /proc/mounts

    try:
        for l in open('/proc/mounts', 'r'):
            (
                _,
                mnt,
                fstype,
                options,
                _,
                _,
            ) = l.split(' ')
            if mnt == '/var/lib/docker/devicemapper':
                driver = 'devicemapper'
                break
            elif mnt == '/var/lib/docker/btrfs':
                driver = 'btrfs'
                break
            elif mnt == '/var/lib/docker/aufs':
                driver = 'aufs'
                break
    except Exception:
        logger.debug('Could not read /proc/mounts')

    if driver in ('btrfs', 'devicemapper', 'aufs'):
        return driver

    # Step 1.b, get it from /proc/mounts but allow
    # some more freedom in the mount point.

    try:
        for l in open('/proc/mounts', 'r'):
            (
                _,
                mnt,
                fstype,
                options,
                _,
                _,
            ) = l.split(' ')
            if 'docker' in mnt and 'devicemapper' in mnt:
                driver = 'devicemapper'
                break
            elif 'docker' in mnt and 'btrfs' in mnt:
                driver = 'btrfs'
                break
            elif 'docker' in mnt and 'aufs' in mnt:
                driver = 'aufs'
                break
    except Exception:
        logger.debug('Could not read /proc/mounts')
    if driver in ('btrfs', 'devicemapper', 'aufs'):
        return driver

    # Step 2, get it from "docker info"

    try:
        proc = subprocess.Popen(
            "docker info | grep 'Storage Driver' | awk -F: '{print $2}'",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        driver = proc.stdout.read().strip()
    except Exception:
        logger.debug('Could not run docker info')

    # Step 3, we default to "devicemapper" (last resort)

    if driver not in ('btrfs', 'devicemapper', 'aufs', 'vfs'):

        # We will take our risk and default to devicemapper

        driver = 'devicemapper'
    return driver


def get_docker_container_json_logs_path(long_id, inspect=None):
    """
    Returns the path to a container (with ID=long_id) docker logs file in the
    docker host file system.

    There are 2 big potential problems with this:

    1. This assumes that the docker Logging Driver is `json-file`. Other
    drivers are detailed here:
    https://docs.docker.com/engine/reference/logging/overview/

    2. This is an abstraction violation as we are breaking the Docker
    abstraction barrier. But, it is so incredibly useful to do this kind of
    introspection that we are willing to pay the price.
    """
    # First try is the default location

    path = '/var/lib/docker/containers/%s/%s-json.log' % (long_id,
                                                          long_id)
    if os.path.isfile(path):
        return path

    # Second try is to get docker inspect LogPath

    if not inspect:
        inspect = exec_dockerinspect(long_id)

    try:
        path = inspect['LogPath']
    except KeyError:
        path = '<no value>'

    if path != '<no value>' and os.path.isfile(path):
        return path

    # Third try is to guess the LogPath based on the HostnamePath
    try:
        path = inspect['HostnamePath']
        path = os.path.join(os.path.dirname(path), '%s-json.log'
                            % long_id)
    except KeyError:
        path = '<no value>'

    if path != '<no value>' and os.path.isfile(path):
        return path

    raise DockerutilsNoJsonLog('Container %s does not have a json log.' % long_id)


def _get_docker_server_version():
    """Run the `docker info` command to get server version
    """
    proc = subprocess.Popen("docker info | grep 'Server Version' | cut -d':' -f2 ", shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    server_version = proc.stdout.read().strip()
    (out, err) = proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError('Could not run docker info command')
    return server_version


def get_docker_container_rootfs_path(long_id, inspect=None):
    """
    Returns the path to a container root (with ID=long_id) in the docker host
    file system.

    This is an abstraction violation as we are breaking the Docker abstraction
    barrier. But, it is so incredibly useful to do this kind of introspection
    that we are willing to pay the price.

    FIXME The mount has to be a `shared mount`, otherwise the container
    rootfs will not be accessible from the host. As an example, in Docker v
    1.7.1 the daemon is started like this:

        unshare -m -- /usr/bin/docker -d

    This means that for a device mapper driver, whenever the docker daemon
    mounts a dm device, this mount will only be accessible to the docker
    daemon and containers.
    """
    driver = get_docker_storage_driver()

    server_version = _get_docker_server_version()
    if server_version == "":
        server_version = "1.9.0"

    # should be debug, for now info
    logger.info('get_docker_container_rootfs_path: long_id=' +
                long_id + ', deriver=' + driver +
                ', server_version=' + server_version)

    if driver == 'devicemapper':

        if not inspect:
            inspect = exec_dockerinspect(long_id)

        pid = str(inspect['State']['Pid'])

        # XXX this looks ugly and brittle
        proc = subprocess.Popen(
            'awk \'{if ($2 == "/" && $1 != "rootfs") print $1}\' /proc/' +
            pid +
            "/mounts | xargs grep /proc/mounts -e | awk '{print $2}'",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        rootfs_path = proc.stdout.read().strip() + '/rootfs'

    elif driver == 'btrfs':

        # XXX this looks ugly and brittle
        if VERSION_SPEC.match(semantic_version.Version(server_version)):
            proc = subprocess.Popen(
                "cat /var/lib/docker/image/btrfs/layerdb/mounts/" +
                long_id +
                "/init-id | cut -d'-' -f1",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            btrfs_path = proc.stdout.read().strip()
            rootfs_path = '/var/lib/docker/btrfs/subvolumes/' + btrfs_path
        else:
            proc = subprocess.Popen(
                'btrfs subvolume list /var/lib/docker | ' +
                'grep ' +
                long_id +
                " | awk '{print $NF}' | grep -v 'init' |  head -n 1",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            btrfs_path = proc.stdout.read().strip()
            rootfs_path = '/var/lib/docker/' + btrfs_path

    elif driver == 'aufs':
        if VERSION_SPEC.match(semantic_version.Version(server_version)):
            proc = subprocess.Popen(
                'cat `find /var/lib/docker -name "' +
                long_id +
                '*" | grep mounts`/init-id',
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            root_dir = proc.stdout.read().strip().split('-')[0]
            rootfs_path = '/var/lib/docker/aufs/mnt/{}'.format(root_dir)
        else:
            proc = subprocess.Popen(
                "find /var/lib/docker -name \"{}*\" | grep mnt | grep -v 'init' | head -n 1".format(
                    long_id),
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            rootfs_path = proc.stdout.read().strip()

    elif driver == 'vfs':
        proc = subprocess.Popen(
            "cat /var/lib/docker/image/vfs/layerdb/mounts/" +
            long_id +
            "/init-id | cut -d'-' -f1",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        vfs_path = proc.stdout.read().strip()
        rootfs_path = '/var/lib/docker/vfs/dir/' + vfs_path

    else:

        raise RuntimeError('Not supported docker storage driver.')

    return rootfs_path
