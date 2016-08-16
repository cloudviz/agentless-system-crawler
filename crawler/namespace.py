#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import multiprocessing
import Queue
import logging
import sys
import types
import signal
import ctypes
import cPickle as pickle
import misc
from crawler_exceptions import (CrawlTimeoutError,
                                CrawlError,
                                NamespaceFailedMntSetns)

logger = logging.getLogger('crawlutils')

try:
    libc = ctypes.CDLL('libc.so.6')
except Exception as e:
    logger.warning('Can not crawl containers as there is no libc: %s' % e)
    libc = None


ALL_NAMESPACES = 'user pid uts ipc net mnt'.split()
IN_CONTAINER_TIMEOUT = 30


def get_errno_msg():
    try:
        libc.__errno_location.restype = ctypes.POINTER(ctypes.c_int)
        errno = libc.__errno_location().contents.value
        errno_msg = os.strerror(errno)
        return errno_msg
    except (OSError, AttributeError):
        pass
    return 'unknown error'


def get_libc():
    global libc
    return libc

def get_pid_namespace(pid):
    try:
        ns = os.stat('/proc/' + str(pid) + '/ns/pid').st_ino
        return ns
    except OSError:
        logger.debug('There is no container with pid=%s running.'
                     % pid)
        return None


class ProcessContext:

    def __init__(self, pid, namespaces):
        self.namespaces = namespaces
        self.pid = pid

    def attach(self):
        # Just to be sure log rotation does not happen in the container

        logging.disable(logging.CRITICAL)
        try:
            self.host_ns_fds = {}
            self.container_ns_fds = {}
            self.host_cwd = os.getcwd()
            open_process_namespaces('self', self.host_ns_fds,
                                    self.namespaces)
            open_process_namespaces(self.pid, self.container_ns_fds,
                                    self.namespaces)
        except Exception as e:
            logging.disable(logging.NOTSET)
            logger.exception(e)
            raise

        try:
            attach_to_process_namespaces(self.container_ns_fds,
                                         self.namespaces)
        except Exception as e:
            logging.disable(logging.NOTSET)
            error_msg = (
                'Could not attach to the pid=%s container mnt namespace. '
                'Exception: %s' % (self.pid, e))
            logger.error(error_msg)
            self.detach()
            raise

    def detach(self):
        try:
            # Re-attach to the process original namespaces before attaching the
            # first time to self.pid namespaces.
            attach_to_process_namespaces(self.host_ns_fds,
                                         self.namespaces)
        except Exception as e:
            logging.disable(logging.NOTSET)
            logger.error('Could not move back to the host: %s' % e)
            # XXX can't recover from this one. But it would be better to
            # bubble up the error.
            sys.exit(1)

        # We are now in host context
        os.chdir(self.host_cwd)

        logging.disable(logging.NOTSET)
        close_process_namespaces(self.container_ns_fds,
                                 self.namespaces)
        close_process_namespaces(self.host_ns_fds, self.namespaces)


def run_as_another_namespace(
    pid,
    namespaces,
    function,
    *args,
    **kwargs
):
    hack_to_pre_load_modules()

    context = ProcessContext(pid, namespaces)
    context.attach()
    try:
        queue = multiprocessing.Queue(2 ** 15)
    except OSError:
        # try again with a smaller queue
        queue = multiprocessing.Queue(2 ** 14)

    child_process = multiprocessing.Process(
        name='crawler-%s' %
        pid, target=function_wrapper, args=(
            queue, function, args), kwargs=kwargs)
    child_process.start()

    child_exception = None
    try:
        (result, child_exception) = queue.get(timeout=IN_CONTAINER_TIMEOUT)
    except Queue.Empty:
        child_exception = CrawlTimeoutError()
    except Exception:
        result = None

    if child_exception:
        result = None

    child_process.join(IN_CONTAINER_TIMEOUT)

    # The join failed and the process might still be alive

    if child_process.is_alive():
        errmsg = ('Timed out waiting for process %d to exit.' %
                  child_process.pid)
        queue.close()
        os.kill(child_process.pid, 9)
        context.detach()
        logger.error(errmsg)
        raise CrawlTimeoutError(errmsg)

    context.detach()

    if result is None:
        if child_exception:
            raise child_exception
        raise CrawlError('Unknown crawl error.')
    return result


def function_wrapper(
    queue,
    function,
    *args,
    **kwargs
):

    # Die if the parent dies
    PR_SET_PDEATHSIG = 1
    get_libc().prctl(PR_SET_PDEATHSIG, signal.SIGHUP)

    def signal_handler_sighup(*args):
        logger.warning('Crawler parent process died, so exiting... Bye!')
        queue.close()
        exit(1)

    signal.signal(signal.SIGHUP, signal_handler_sighup)

    result = None
    try:
        args = args[0]
        result = function(*args)

        # if res is a generator (i.e. function uses yield)

        if isinstance(result, types.GeneratorType):
            result = list(result)
        queue.put((result, None))
        queue.close()
        sys.exit(0)
    except Exception as e:
        queue.put((None, e))
        queue.close()
        sys.exit(1)


def hack_to_pre_load_modules():
    queue = multiprocessing.Queue()

    def foo(queue):
        queue.put('dummy')
        pass

    p = multiprocessing.Process(target=foo, args=(queue, ))
    p.start()
    queue.get()
    p.join()


def open_process_namespaces(pid, namespace_fd, namespaces):
    for ct_ns in namespaces:
        try:

            # arg 0 means readonly
            namespace_fd[ct_ns] = get_libc().open('/proc/' + pid + '/ns/' +
                                                  ct_ns, 0)
            if namespace_fd[ct_ns] == -1:
                errno_msg = get_errno_msg()
                error_msg = 'Opening the %s namespace file failed: %s' \
                    % (ct_ns, errno_msg)
                logger.warning(error_msg)
                if ct_ns == 'mnt':
                    raise NamespaceFailedMntSetns(error_msg)
        except Exception as e:
            error_msg = 'The open() syscall failed with: %s' % e
            logger.warning(error_msg)
            if ct_ns == 'mnt':
                raise e


def close_process_namespaces(namespace_fd, namespaces):
    for ct_ns in namespaces:
        r = get_libc().close(namespace_fd[ct_ns])
        if r == -1:
            errno_msg = get_errno_msg()
            error_msg = ('Could not close the %s '
                         'namespace (fd=%s): %s' %
                         (ct_ns, namespace_fd[ct_ns], errno_msg))
            logger.warning(error_msg)


def attach_to_process_namespaces(namespace_fd, ct_namespaces):
    for ct_ns in ct_namespaces:
        try:
            if hasattr(get_libc(), 'setns'):
                r = get_libc().setns(namespace_fd[ct_ns], 0)
            else:
                # The Linux kernel ABI should be stable enough
                __NR_setns = 308
                r = get_libc().syscall(__NR_setns, namespace_fd[ct_ns], 0)
            if r == -1:
                errno_msg = get_errno_msg()
                error_msg = ('Could not attach to the container %s '
                             'namespace (fd=%s): %s' %
                             (ct_ns, namespace_fd[ct_ns], errno_msg))
                logger.warning(error_msg)
                if ct_ns == 'mnt':
                    raise NamespaceFailedMntSetns(error_msg)
        except Exception as e:
            error_msg = 'The setns() syscall failed with: %s' % e
            logger.warning(error_msg)
            if ct_ns == 'mnt':
                logger.exception(e)
                raise e
