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
import ctypes

# Additional modules

# External dependencies that must be pip install'ed separately

from netifaces import interfaces, ifaddresses, AF_INET

logger = logging.getLogger('crawlutils')


def subprocess_run(cmd, good_rc=0, shell=True):
    """
    Runs cmd_string as a shell command. It returns stdout as a string, and
    raises RuntimeError if the return code is not equal to `good_rc`.

    It returns the tuple: (stdout, stderr, returncode)
    Can raise AttributeError or RuntimeError:
    """
    try:
        proc = subprocess.Popen(
                    cmd,
                    shell=shell,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE)
        (out, err) = proc.communicate()
        rc = proc.returncode
    except OSError as exc:
        raise RuntimeError('Failed to launch dpkg query for packages. Check if '
                'dpkg-query is installed: [Errno: %d] ' %
                exc.errno + exc.strerror + ' [Exception: ' +
                type(exc).__name__ + ']')
    if rc != good_rc:
        raise RuntimeError('(%s) failed with rc=%s: %s' %
                           (cmd, rc, err))
    return out


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

    Can raise RuntimeError if there are no btrfs tools installed.
    """
    out = subprocess_run('btrfs subvolume list ' + path)

    for line in out.strip():
        submodule = line.split()
        if len(submodule) != 8:
            raise RuntimeError('Expecting the output of `btrfs subvolume` to'
                               ' have 8 columns. Received this: %s' % line)
        yield submodule
