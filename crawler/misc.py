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


def subprocess_run(cmd, ignore_failure=False, shell=True):
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
        out, err = proc.communicate()
        rc = proc.returncode

    except OSError as exc:
        raise RuntimeError('Failed to run ' + cmd + ': [Errno: %d] ' %
                exc.errno + exc.strerror + ' [Exception: ' +
                type(exc).__name__ + ']')
    if (not ignore_failure) and (rc != 0):
        raise RuntimeError('(%s) failed with rc=%s: %s' %
                           (cmd, rc, err))
    return out


def enum(**enums):
    return type('Enum', (), enums)


def get_process_env(pid=1):
    """the environment settings from the processes perpective,
       @return C{dict}
    """

    try:
        pid = int(pid)
    except ValueError:
        raise TypeError('pid has to be an integer')

    env = {}
    envlist = open('/proc/%s/environ' % pid).read().split('\000')
    for e in envlist:
        (k, _, v) = e.partition('=')
        (k, v) = (k.strip(), v.strip())
        if not k:
            continue
        env[k] = v
    return env


def process_is_crawler(pid):
    """This is really checking if proc is the current process.
    """
    try:
        pid = int(pid)
    except ValueError:
        raise TypeError('pid has to be an integer')

    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess as exc:
        # If the process does not exist, then it's definitely not the crawler
        return False

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
    return False


class NullHandler(logging.Handler):

    def emit(self, record):
        pass


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
        pid = int(pid)
    except ValueError:
        raise TypeError('pid has to be an integer')

    try:
        os.kill(pid, 0)
    except OSError as exc:
        if 'not permitted' in str(exc):
            return True
        return False
    else:
        return True


def execution_path(filename):
    # if filename is an absolute path, os.path.join will return filename
    return os.path.join(os.path.dirname(inspect.getfile(sys._getframe(1))),
                        filename)


def btrfs_list_subvolumes(path):
    out = subprocess_run('btrfs subvolume list ' + path)

    for line in out.strip().split('\n'):
        submodule = line.split()
        if len(submodule) != 9:
            raise RuntimeError('Expecting the output of `btrfs subvolume` to'
                               ' have 9 columns. Received this: %s' % line)
        yield submodule
