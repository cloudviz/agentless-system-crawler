#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import sys
import inspect
import logging
import socket
import subprocess
import re
import psutil

# Additional modules

# External dependencies that must be pip install'ed separately

from netifaces import interfaces, ifaddresses, AF_INET

logger = logging.getLogger('crawlutils')


def enum(**enums):
    return type('Enum', (), enums)


def GetProcessEnv(pid=1):
    """the environment settings from the processes perpective,
       @return C{dict}
    """

    env = {}
    try:
        envlist = open('/proc/%s/environ' % pid).read().split('\000')
    except:
        return env
    for e in envlist:
        (k, _, v) = e.partition('=')
        (k, v) = (k.strip(), v.strip())
        if not k:
            continue
        env[k] = v
    return env


def process_is_crawler(proc):
    try:
        cmdline = (proc.cmdline() if hasattr(proc.cmdline, '__call__'
                                             ) else proc.cmdline)

        # curr is the crawler process

        curr = psutil.Process(os.getpid())
        curr_cmdline = (
            curr.cmdline() if hasattr(
                curr.cmdline,
                '__call__') else curr.cmdline)
        if cmdline == curr_cmdline:
            return True
    except Exception:
        pass
    return False


class NullHandler(logging.Handler):

    def emit(self, record):
        pass


def get_errno_msg(libc):
    try:
        import ctypes
        libc.__errno_location.restype = ctypes.POINTER(ctypes.c_int)
        errno = libc.__errno_location().contents.value
        errno_msg = os.strerror(errno)
        return errno_msg
    except Exception:
        return 'unknown error'


# try to determine this host's IP address

def get_host_ipaddr():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('www.ibm.com', 9))
        return s.getsockname()[0]
    except socket.error:
        return socket.gethostname()
    finally:
        del s


def get_host_ip4_addresses():
    ip_list = []
    for interface in interfaces():
        if AF_INET in ifaddresses(interface):
            for link in ifaddresses(interface)[AF_INET]:
                ip_list.append(link['addr'])
    return ip_list


# Find the mountpoint of a given path

def find_mount_point(path):
    path = os.path.abspath(path)
    while not os.path.ismount(path):
        path = os.path.dirname(path)
    return path


# Log the atime configuration of the mount location of the given path
# Return: 'unknown' | 'strictatime' | 'relatime' | 'noatime'

def log_atime_config(path, crawlmode):
    atime_config = 'unknown'
    mountlocation = find_mount_point(path=path)
    logger.info('Mount location for specified crawl root_dir %s: %s'
                % (path, mountlocation))

    # Looking at `mount` for atime config is only meaningful for INVM

    if crawlmode == 'INVM':
        grepstr = 'on %s ' % mountlocation
        try:
            mount = subprocess.Popen('mount', stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
            mountlist = subprocess.Popen(
                ('grep',
                 grepstr),
                stdin=mount.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            mountlist_arr = mountlist.stdout.read().split('\n')
            if len(mountlist_arr) > 0:

                # pick the first one if we found more than one mount location
                # Will look like: "/dev/xvda2 on / type ext3
                # (rw,noatime,errors=remount-ro,barrier=0)"

                ptrn = r'.*?\((.*?)\).*?'
                match = re.search(ptrn, mountlist_arr[0])

                # Get the part in parenthesis and split. WIll look like:
                # "rw,noatime,errors=remount-ro,barrier=0"

                for i in match.group(1).split(','):
                    if i.strip() == 'noatime':
                        atime_config = 'noatime'
                        logger.debug(
                            'Found atime config: %s in mount information, '
                            'updating log' % atime_config)
                        break
                    elif i.strip() == 'relatime':
                        atime_config = 'relatime'
                        logger.debug(
                            'Found atime config: %s in mount information, '
                            'updating log' % atime_config)
                        break
                    elif i.strip() == 'strictatime':
                        atime_config = 'strictatime'
                        logger.debug(
                            'Found atime config: %s in mount information, '
                            'updating log' % atime_config)
                        break

                # If we found a mount location, but did not have atime info in
                # mount. Assume it is the default relatime. As it does not show
                # in mount options by default.

                if atime_config == 'unknown':
                    atime_config = 'relatime'
                    logger.debug(
                        'Did not find any atime config for the matching mount '
                        'location. Assuming: %s' % atime_config)
        except OSError as e:
            logger.error('Failed to query mount information: ' +
                         '[Errno: %d] ' % e.errno + e.strerror +
                         ' [Exception: ' + type(e).__name__ + ']')

    logger.info("Atime configuration for '%s': '%s'" % (mountlocation,
                                                        atime_config))
    if atime_config == 'strictatime':
        logger.info('strictatime: File access times are reflected correctly'
                    )
    if atime_config == 'relatime':
        logger.info(
            'relatime: File access times are only updated after 24 hours')
    if atime_config == 'noatime':
        logger.info('noatime: File access times are never updated properly'
                    )
    if atime_config == 'unknown':
        logger.info(
            'unknown: Could not determine atime config. File atime '
            'information might not be reliable')
    return atime_config


def join_abs_paths(root, appended_root):
    """ Join absolute paths: appended_root is appended after root
    """
    return os.path.normpath(os.path.join(root,
                                         os.path.relpath(appended_root, '/')))


def is_process_running(pid):
    """ Check For the existence of a unix pid.
    """

    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


def execution_path(filename):
    # if filename is an absolute path, os.path.join will return filename
    return os.path.join(os.path.dirname(inspect.getfile(sys._getframe(1))),
                        filename)


def btrfs_list_subvolumes(path):
    """
    Returns a list of submodules, example:
    [
     ['ID', '260', 'gen', '22', 'top', 'level', '5', 'path', 'sub1'],
     ['ID', '260', 'gen', '22', 'top', 'level', '5', 'path', 'sub1/sub2'],
    ]
    """
    proc = subprocess.Popen(
                'btrfs subvolume list ' + path,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
    error_output = proc.stderr.read()
    (out, err) = proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError('btrfs subvolume failed with ' + error_output)

    for line in proc.stdout.read().strip():
        submodule = line.split()
        if len(submodule) != 8:
            raise RuntimeError('btrfs subvolume failed with ' + error_output)
        yield submodule
