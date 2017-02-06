#!usr/bin/python
# -*- coding: utf-8 -*-
import logging
import os

import dateutil.parser as dp
import docker
import semantic_version
import itertools

from utils import misc
from crawler_exceptions import (DockerutilsNoJsonLog,
                                DockerutilsException)
from timeout_utils import (Timeout, TimeoutError)
from dockerevent import DockerContainerEvent

# version at which docker image layer organization changed
VERSION_SPEC = semantic_version.Spec('>=1.10.0')

logger = logging.getLogger('crawlutils')

SUPPORTED_DRIVERS = ['btrfs', 'devicemapper', 'aufs', 'vfs']


def exec_dockerps():
    """
    Returns a list of docker inspect jsons, one for each container.

    This call executes the `docker inspect` command every time it is invoked.
    """
    try:
        client = docker.Client(
            base_url='unix://var/run/docker.sock', version='auto')
        containers = client.containers()
        inspect_arr = []
        for container in containers:
            inspect = exec_dockerinspect(container['Id'])
            inspect_arr.append(inspect)
    except docker.errors.DockerException as e:
        logger.warning(str(e))
        raise DockerutilsException('Failed to exec dockerps')

    return inspect_arr


def exec_docker_history(long_id):
    try:
        client = docker.Client(base_url='unix://var/run/docker.sock',
                               version='auto')
        image = client.inspect_container(long_id)['Image']
        history = client.history(image)
        return history
    except docker.errors.DockerException as e:
        logger.warning(str(e))
        raise DockerutilsException('Failed to exec dockerhistory')


def _reformat_inspect(inspect):
    """Fixes some basic issues with the inspect json returned by docker.
    """
    # For some reason, Docker inspect sometimes returns the pid in scientific
    # notation.
    inspect['State']['Pid'] = '%.0f' % float(inspect['State']['Pid'])

    docker_datetime = dp.parse(inspect['Created'])
    epoch_seconds = docker_datetime.strftime('%s')
    inspect['Created'] = epoch_seconds


def exec_dockerinspect(long_id):
    try:
        client = docker.Client(
            base_url='unix://var/run/docker.sock', version='auto')
        inspect = client.inspect_container(long_id)
        _reformat_inspect(inspect)
    except docker.errors.DockerException as e:
        logger.warning(str(e))
        raise DockerutilsException('Failed to exec dockerinspect')

    try:
        # get the first RepoTag
        inspect['RepoTag'] = client.inspect_image(
            inspect['Image'])['RepoTags'][0]
    except (docker.errors.DockerException, KeyError, IndexError):
        inspect['RepoTag'] = ''

    return inspect


def _get_docker_storage_driver_using_proc_mounts():
    for l in open('/proc/mounts', 'r'):
        _, mnt, _, _, _, _ = l.split(' ')
        for driver in SUPPORTED_DRIVERS:
            if mnt == '/var/lib/docker/' + driver:
                return driver
    raise OSError('Could not find the driver in /proc/mounts')


def _get_docker_storage_driver():
    """
    We will try several steps in order to ensure that we return
    one of the 4 types (btrfs, devicemapper, aufs, vfs).
    """
    driver = None

    # Step 1, get it from "docker info"

    try:
        client = docker.Client(
            base_url='unix://var/run/docker.sock', version='auto')
        driver = client.info()['Driver']
    except (docker.errors.DockerException, KeyError):
        pass  # try to continue with the default of 'devicemapper'

    if driver in SUPPORTED_DRIVERS:
        return driver

    # Step 2, get it from /proc/mounts

    try:
        driver = _get_docker_storage_driver_using_proc_mounts()
    except (OSError, IOError):
        logger.debug('Could not read /proc/mounts')

    if driver in SUPPORTED_DRIVERS:
        return driver

    # Step 3, we default to "devicemapper" (last resort)

    if driver not in SUPPORTED_DRIVERS:

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

    path = None
    try:
        path = inspect['LogPath']
    except KeyError:
        pass

    if path and os.path.isfile(path):
        return path

    # Third try is to guess the LogPath based on the HostnamePath

    path = None
    try:
        path = inspect['HostnamePath']
        path = os.path.join(os.path.dirname(path), '%s-json.log'
                            % long_id)
    except KeyError:
        pass

    if path and os.path.isfile(path):
        return path

    raise DockerutilsNoJsonLog(
        'Container %s does not have a json log.' %
        long_id)


def _get_docker_server_version():
    """Run the `docker info` command to get server version
    """
    try:
        client = docker.Client(
            base_url='unix://var/run/docker.sock', version='auto')
        return client.version()['Version']
    except (docker.errors.DockerException, KeyError) as e:
        logger.warning(str(e))
        raise DockerutilsException('Failed to get the docker version')


try:
    server_version = _get_docker_server_version()
    driver = _get_docker_storage_driver()
except DockerutilsException:
    server_version = None
    driver = None


def _get_container_rootfs_path_dm(long_id, inspect=None):

    if not inspect:
        inspect = exec_dockerinspect(long_id)

    pid = str(inspect['State']['Pid'])

    rootfs_path = None
    device = None
    try:
        with open('/proc/' + pid + '/mounts', 'r') as f:
            for line in f:
                _device, _mountpoint, _, _, _, _ = line.split()
                if _mountpoint == '/' and _device != 'rootfs':
                    device = _device
        with open('/proc/mounts', 'r') as f:
            for line in f:
                _device, _mountpoint, _, _, _, _ = line.split()
                if device in line and _mountpoint != '/':
                    rootfs_path = _mountpoint
                    break
    except IOError as e:
        logger.warning(str(e))
    if not rootfs_path or rootfs_path == '/':
        raise DockerutilsException('Failed to get rootfs on devicemapper')

    return rootfs_path + '/rootfs'


def _get_container_rootfs_path_btrfs(long_id, inspect=None):

    rootfs_path = None

    if VERSION_SPEC.match(semantic_version.Version(server_version)):
        btrfs_path = None
        mountid_path = ('/var/lib/docker/image/btrfs/layerdb/mounts/' +
                        long_id + '/mount-id')
        try:
            with open(mountid_path, 'r') as f:
                btrfs_path = f.read().strip()
        except IOError as e:
            logger.warning(str(e))
        if not btrfs_path:
            raise DockerutilsException('Failed to get rootfs on btrfs')
        rootfs_path = '/var/lib/docker/btrfs/subvolumes/' + btrfs_path
    else:
        btrfs_path = None
        try:
            for submodule in misc.btrfs_list_subvolumes('/var/lib/docker'):
                _, _, _, _, _, _, _, _, mountpoint = submodule
                if (long_id in mountpoint) and ('init' not in mountpoint):
                    btrfs_path = mountpoint
                    break
        except RuntimeError:
            pass
        if not btrfs_path:
            raise DockerutilsException('Failed to get rootfs on btrfs')
        rootfs_path = '/var/lib/docker/' + btrfs_path

    return rootfs_path


def _get_container_rootfs_path_aufs(long_id, inspect=None):

    rootfs_path = None

    if VERSION_SPEC.match(semantic_version.Version(server_version)):
        aufs_path = None
        mountid_path = ('/var/lib/docker/image/aufs/layerdb/mounts/' +
                        long_id + '/mount-id')
        try:
            with open(mountid_path, 'r') as f:
                aufs_path = f.read().strip()
        except IOError as e:
            logger.warning(str(e))
        if not aufs_path:
            raise DockerutilsException('Failed to get rootfs on aufs')
        rootfs_path = '/var/lib/docker/aufs/mnt/' + aufs_path
    else:
        rootfs_path = None
        for _path in ['/var/lib/docker/aufs/mnt/' + long_id,
                      '/var/lib/docker/aufs/diff/' + long_id]:
            if os.path.isdir(_path) and os.listdir(_path):
                rootfs_path = _path
                break
        if not rootfs_path:
            raise DockerutilsException('Failed to get rootfs on aufs')

    return rootfs_path


def _get_container_rootfs_path_vfs(long_id, inspect=None):

    rootfs_path = None

    vfs_path = None
    mountid_path = ('/var/lib/docker/image/vfs/layerdb/mounts/' +
                    long_id + '/mount-id')
    try:
        with open(mountid_path, 'r') as f:
            vfs_path = f.read().strip()
    except IOError as e:
        logger.warning(str(e))
    if not vfs_path:
        raise DockerutilsException('Failed to get rootfs on vfs')

    rootfs_path = '/var/lib/docker/vfs/dir/' + vfs_path

    return rootfs_path


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
    global server_version
    global driver

    rootfs_path = None

    if (not server_version) or (not driver):
        raise DockerutilsException('Not supported docker storage driver.')

    # should be debug, for now info
    logger.info('get_docker_container_rootfs_path: long_id=' +
                long_id + ', deriver=' + driver +
                ', server_version=' + server_version)

    if driver == 'devicemapper':
        rootfs_path = _get_container_rootfs_path_dm(long_id, inspect)
    elif driver == 'btrfs':
        rootfs_path = _get_container_rootfs_path_btrfs(long_id, inspect)
    elif driver == 'aufs':
        rootfs_path = _get_container_rootfs_path_aufs(long_id, inspect)
    elif driver == 'vfs':
        rootfs_path = _get_container_rootfs_path_vfs(long_id, inspect)
    else:
        raise DockerutilsException('Not supported docker storage driver.')

    return rootfs_path


def poll_container_create_events(timeout=0.1):
    try:
        client = docker.Client(base_url='unix://var/run/docker.sock',
                               version='auto')
        filters = dict()
        filters['type'] = 'container'
        filters['event'] = 'start'
        events = client.events(filters=filters, decode=True)
        with Timeout(seconds=timeout):
            # we are expecting a single event
            event = list(itertools.islice(events, 1))[0]

        containerid = event['id']
        imageid = event['from']
        epochtime = event['time']
        cEvent = DockerContainerEvent(containerid, imageid,
                                      event['Action'], epochtime)
        return cEvent
    except docker.errors.DockerException as e:
        logger.warning(str(e))
        raise DockerutilsException('Failed to exec dockerhistory')
    except TimeoutError:
        logger.info("Container event timeout")
        pass

    return None
