#!usr/bin/python
# -*- coding: utf-8 -*-
import os
import logging
import subprocess

# External dependencies that must be easy_install'ed separately

import simplejson as json

from dockercontainer import DockerContainer

try:
    import docker
except ImportError:
    docker = None

logger = logging.getLogger('crawlutils')


def _get_pid_namespace(pid):
    try:
        ns = os.stat('/proc/' + str(pid) + '/ns/pid').st_ino
        return ns
    except Exception:
        logger.debug('The container with pid=%s is not present anymore'
                     % pid)
        return None


def list_docker_containers():

    # TODO: Somehow subscribe to Docker events, so we can keep the containers
    # list up to date without having to poll like this.
    return exec_dockerps()


def exec_dockerps():
    try:
        if docker is None:
            raise ImportError("Please install the Docker python client.")

        client = docker.Client(base_url='unix://var/run/docker.sock')
        containers = client.containers()
        for container in containers:  # docker ps
            inspect = client.inspect_container(container['Id'])
            yield DockerContainer.fromInspect(inspect)
        del client
        return
    except Exception as e:
        print e
        logger.warning(e)

    # If we are here it is most liekly because of a version mismatch. Anyway,
    # let's call the command directly as another process.

    logger.warning(
        'Talking to docker over the socket failed, will have to call the '
        'docker ps command.')

    proc = subprocess.Popen('docker ps -q', shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    short_id_list = proc.stdout.read().strip().split()

    proc = subprocess.Popen('docker inspect %s'
                            % ' '.join(short_id_list), shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    inspect_data = proc.stdout.read().strip()
    inspect_arr = json.loads(inspect_data)
    for inspect in inspect_arr:
        yield DockerContainer.fromInspect(inspect)


def exec_docker_history(long_id=None):
    if not long_id:
        raise Exception('This function needs a docker long_id')

    # Let's try Docker API first

    try:
        if docker is None:
            raise ImportError("Please install the Docker python client.")

        client = docker.Client(base_url='unix://var/run/docker.sock')
        containers = client.containers()
        out = None
        for c in containers:
            if long_id == c['Id']:
                image = c['Image']
                # The returned Image field is sometimes 'ID:tag' which can't
                # be used to query in client.history()
                if ':' in image:
                    image = image.split(':')[0]
                out = client.history(image)
        del client
    except Exception as e:
        logger.error(e)
    else:
        return out

    # If we can't talk to docker through the socket, we have no other choice
    # than using the docker command.

    proc = subprocess.Popen('docker inspect --format {{.Image}} %s'
                            % long_id, shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    image_id = proc.stdout.read().strip()
    try:
        history = _get_docker_image_history_slow(image_id)
        return history
    except Exception as e:
        logger.error('Error executing docker history', exc_info=True)
        raise e


def _get_docker_image_history_slow(image_id):
    proc = subprocess.Popen('docker history -q --no-trunc %s'
                            % image_id, shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    history_img_ids = proc.stdout.read().split()

    proc = subprocess.Popen('docker inspect %s'
                            % ' '.join(history_img_ids), shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    image_history = []
    inspect_data = proc.stdout.read()
    inspect_arr = json.loads(inspect_data)

    # XXX json load can fail

    for inspect in inspect_arr:

        # XXX what if inspect doesn;t have some of these fields

        image_info = {'Tags': None,
                      'Size': inspect['Size'],
                      'Id': inspect['Id'],
                      'CreatedBy': inspect['ContainerConfig']['Cmd'],
                      'Created': inspect['Created']}
        image_history.append(image_info)
    return image_history


def _reformat_inspect(inspect):

    def fold_port_key(ports_dict):
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

    np = fold_port_key(inspect['NetworkSettings']['Ports'])
    if np:
        inspect['NetworkSettings']['Ports'] = np

    np = fold_port_key(inspect['HostConfig']['PortBindings'])
    if np:
        inspect['HostConfig']['PortBindings'] = np


def exec_dockerinspect(long_id):
    logger.debug('Crawling docker inspect')

    # Let's try Docker API first

    try:
        if docker is None:
            raise ImportError("Please install the Docker python client.")

        client = docker.Client(base_url='unix://var/run/docker.sock')
        containers = client.containers()
        out = None
        for c in containers:  # docker ps
            if not long_id or long_id == c['Id']:
                inspect = client.inspect_container(c['Id'])
                _reformat_inspect(inspect)
                out = inspect
        del client
        return out
    except Exception as e:
        logger.error(e)

    try:
        proc = subprocess.Popen('docker inspect %s' % long_id,
                                shell=True, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        inspect_data = proc.stdout.read().strip()
        (out, err) = proc.communicate()
        if proc.returncode != 0:

            # There is no docker command (or it just failed).

            raise BaseException('Could not run docker inspect')

        inspect = json.loads(inspect_data)[0]
        _reformat_inspect(inspect)
        return inspect
    except Exception as e:
        logger.error('Error executing dockerinspect', exc_info=True)
        raise


def get_docker_container_logs_path(long_id):

    # First try is the default location

    path = '/var/lib/docker/containers/%s/%s-json.log' % (long_id,
                                                          long_id)
    if os.path.isfile(path):
        return path
    try:

        # Second try is to get docker inspect LogPath

        proc = \
            subprocess.Popen("docker inspect --format '{{.LogPath}}' %s"
                             % long_id, shell=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        path = proc.stdout.read().strip()
        if path != '<no value>' and os.path.isfile(path):
            return path

        # Third try is to use the HostnamePath

        proc = \
            subprocess.Popen("docker inspect --format '{{.HostnamePath}}' %s"
                             % long_id, shell=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        path = proc.stdout.read().strip()
        if path == '<no value>':
            raise IOError(
                'Container %s does not have a docker inspect .HostnamePath' %
                long_id)
        path = os.path.join(os.path.dirname(path), '%s-json.log'
                            % long_id)
        if os.path.isfile(path):
            return path
    except Exception as e:
        raise e


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

    if driver not in ('btrfs', 'devicemapper', 'aufs'):

        # We will take our risk and default to devicemapper

        driver = 'devicemapper'
    return driver


def get_docker_container_rootfs_path(c):
    driver = get_docker_storage_driver()

    if driver == 'devicemapper':

        # We don't support devicemapper loop-lvm mode.

        try:
            proc = subprocess.Popen(
                "docker info | grep -c 'Data loop file'",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            loop_lvm_mode = proc.stdout.read().strip()
            if loop_lvm_mode != '0':
                raise RuntimeError('Not supported docker storage driver.'
                                   )
        except Exception:
            logger.debug('Could not run docker info')

        proc = subprocess.Popen(
            'awk \'{if ($2 == "/" && $1 != "rootfs") print $1}\' /proc/' +
            c.pid +
            "/mounts | xargs grep /proc/mounts -e | awk '{print $2}'",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        rootfs_path = proc.stdout.read().strip() + '/rootfs'
    elif driver == 'btrfs':

        proc = subprocess.Popen(
            'btrfs subvolume list /var/lib/docker | ' +
            'grep ' +
            c.long_id +
            " | awk '{print $NF}' | grep -v 'init' |  head -n 1",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        btrfs_path = proc.stdout.read().strip()
        rootfs_path = '/var/lib/docker/' + btrfs_path
    else:

        raise RuntimeError('Not supported docker storage driver.')

    return rootfs_path
