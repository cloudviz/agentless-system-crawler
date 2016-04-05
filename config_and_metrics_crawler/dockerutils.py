#!usr/bin/python
# -*- coding: utf-8 -*-
import os
import logging
import subprocess
import json
import dateutil.parser as dp
import semantic_version

VERSION_SPEC = semantic_version.Spec('>=1.10.0') # version at which docker image layer organization changed

# External dependencies that must be pip install'ed separately

try:
    import docker
except ImportError:
    docker = None

logger = logging.getLogger('crawlutils')


def exec_dockerps():
    try:
        return _exec_dockerps()
    except Exception as e:
        logger.warning('Talking to docker over the socket failed: %s' % e)

    try:
        return _exec_dockerps_slow()
    except Exception as e:
        logger.exception(e)

    return []


def _exec_dockerps():
    """
    Returns a list of docker inspect jsons, one for each container.

    This call executes the `docker inspect` command every time it is invoked.
    """
    if docker is None:
        raise ImportError('Please install the Docker python client.')

    client = docker.Client(base_url='unix://var/run/docker.sock')
    containers = client.containers()
    inspect_arr = []
    for container in containers:  # docker ps
        inspect = client.inspect_container(container['Id'])
        _reformat_inspect(inspect)
        inspect_arr.append(inspect)

    # Is this needed?
    del client

    return inspect_arr


def _exec_dockerps_slow():
    """Run the `docker ps` command as a subprocess.
    """
    proc = subprocess.Popen('docker ps -q', shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    short_id_list = proc.stdout.read().strip().split()
    (out, err) = proc.communicate()
    if proc.returncode != 0:

        # There is no docker command (or it just failed).

        raise RuntimeError('Could not run docker command')

    proc = subprocess.Popen('docker inspect %s'
                            % ' '.join(short_id_list), shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    inspect_data = proc.stdout.read().strip()
    (out, err) = proc.communicate()
    if proc.returncode != 0:

        # There is no docker command (or it just failed).

        raise RuntimeError('Could not run docker command')

    inspect_arr = json.loads(inspect_data)
    for inspect in inspect_arr:
        _reformat_inspect(inspect)

    return inspect_arr


def exec_docker_history(long_id=None):
    try:
        return _exec_docker_history(long_id)
    except Exception as e:
        # check what exceptions can the docker client raise
        logger.warning('Talking to docker over the socket failed: %s' % e)

    try:
        return _exec_docker_history_slow(long_id)
    except Exception as e:
        logger.exception(e)

    return []


def _exec_docker_history(long_id=None):
    if docker is None:
        raise ImportError('Please install the Docker python client.')

    client = docker.Client(base_url='unix://var/run/docker.sock')
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


def _exec_docker_history_slow(long_id=None):
    proc = subprocess.Popen('docker inspect --format {{.Image}} %s'
                            % long_id, shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    image_id = proc.stdout.read().strip()
    (out, err) = proc.communicate()
    if proc.returncode != 0:

        # There is no docker command (or it just failed).

        raise RuntimeError('Could not run docker command')

    try:
        history = _get_docker_image_history_slow(image_id)
        return history
    except Exception:
        logger.error('Error executing docker history', exc_info=True)
        raise


def _get_docker_image_history_slow(image_id):
    proc = subprocess.Popen('docker history -q --no-trunc %s'
                            % image_id, shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    history_img_ids = proc.stdout.read().split()
    (out, err) = proc.communicate()
    if proc.returncode != 0:

        # There is no docker command (or it just failed).

        raise RuntimeError('Could not run docker command')

    # Filter out <missing> image IDs
    history_img_ids = [img for img in history_img_ids if '<missing>' != img]

    proc = subprocess.Popen('docker inspect %s'
                            % ' '.join(history_img_ids), shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    image_history = []
    inspect_data = proc.stdout.read()
    (out, err) = proc.communicate()
    if proc.returncode != 0:

        # There is no docker command (or it just failed).

        raise RuntimeError('Could not run docker command')

    inspect_arr = json.loads(inspect_data)

    # XXX json load can fail

    for inspect in inspect_arr:

        # XXX what if inspect doesn;t have some of these fields
        docker_datetime = dp.parse(inspect['Created'])
        epoch_seconds = docker_datetime.strftime('%s')

        image_info = {'Tags': None,
                      'Size': inspect['Size'],
                      'Id': inspect['Id'],
                      'CreatedBy': inspect['ContainerConfig']['Cmd'],
                      'Created': epoch_seconds}
        image_history.append(image_info)
    return image_history


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
    try:
        return _exec_dockerinspect(long_id)
    except Exception as e:
        # check what exceptions can the docker client raise
        logger.warning('Talking to docker over the socket failed: %s' % e)

    try:
        return _exec_dockerinspect_slow(long_id)
    except Exception as e:
        logger.exception(e)

    return {}


def _exec_dockerinspect(long_id):
    if docker is None:
        raise ImportError('Please install the Docker python client.')

    client = docker.Client(base_url='unix://var/run/docker.sock')
    containers = client.containers()
    out = None
    for c in containers:  # docker ps
        if not long_id or long_id == c['Id']:
            inspect = client.inspect_container(c['Id'])
            _reformat_inspect(inspect)
            out = inspect
            break
    del client
    return out


def _exec_dockerinspect_slow(long_id):
    try:
        proc = subprocess.Popen('docker inspect %s' % long_id,
                                shell=True, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        inspect_data = proc.stdout.read().strip()
        (out, err) = proc.communicate()
        if proc.returncode != 0:

            # There is no docker command (or it just failed).

            raise RuntimeError('Could not run docker command')

        inspect = json.loads(inspect_data)[0]
        _reformat_inspect(inspect)
        return inspect
    except Exception:
        logger.error('Error executing dockerinspect', exc_info=True)
        raise


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
            "sudo docker info | grep 'Storage Driver' | awk -F: '{print $2}'",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        driver = proc.stdout.read().strip()
    except Exception:
        logger.debug('Could not run docker info')

    # Step 3, we default to "devicemapper" (last resort)

    if driver not in ('btrfs', 'devicemapper', 'aufs'):

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

    #this should be in debug mode, for now info: sastry
    logger.info('get_docker_container_json_logs_path: long_id=' +
        long_id + 'inspect=' + inspect)
    path = inspect['LogPath']

    if path == '<no value>' or not os.path.isfile(path):
        path = inspect['HostnamePath']

    if path == '<no value>':
        raise IOError(
            'Container %s does not have a docker inspect .HostnamePath' %
            long_id)

    path = os.path.join(os.path.dirname(path), '%s-json.log'
                        % long_id)

    if os.path.isfile(path):
        return path


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
        logger.info('get_docker_container_rootfs_path: long_id=' +
            long_id + ', inspect=' + inspect)

        pid = inspect['State']['Pid']

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
                "sudo cat /var/lib/docker/image/btrfs/layerdb/mounts/" +
                long_id +
                "/init-id | cut -d'-' -f1",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            btrfs_path = proc.stdout.read().strip()
            rootfs_path = '/var/lib/docker/btrfs/subvolumes/' + btrfs_path
        else:
            proc = subprocess.Popen(
                'sudo btrfs subvolume list /var/lib/docker | ' +
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
                'sudo cat `find /var/lib/docker -name "'+
                long_id +
                '*" | grep mounts`/init-id',
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            root_dir  = proc.stdout.read().strip().split('-')[0]
            rootfs_path = '/var/lib/docker/aufs/mnt/{}'.format(root_dir)
        else: 
            proc = subprocess.Popen(
                "sudo find /var/lib/docker -name \"{}*\" | grep mnt | grep -v 'init' | head -n 1".format(long_id),
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            rootfs_path = proc.stdout.read().strip()
    else:

        raise RuntimeError('Not supported docker storage driver.')

    return rootfs_path
