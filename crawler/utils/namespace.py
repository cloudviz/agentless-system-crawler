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
from crawler_exceptions import (CrawlTimeoutError,
                                CrawlError,
                                NamespaceFailedSetns)

logger = logging.getLogger('crawlutils')

try:
    libc = ctypes.CDLL('libc.so.6')
except Exception as e:
    logger.warning('Can not crawl containers as there is no libc: %s' % e)
    libc = None


ALL_NAMESPACES = 'user pid uts ipc net mnt'.split()
IN_PROCESS_TIMEOUT = 30


def get_errno_msg():
    try:
        libc.__errno_location.restype = ctypes.POINTER(ctypes.c_int)
        errno = libc.__errno_location().contents.value
        errno_msg = os.strerror(errno)
        return errno_msg
    except (OSError, AttributeError):
        # Getting an error while trying to get the errorno
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
        self.host_ns_fds = {}
        self.container_ns_fds = {}
        self.host_cwd = os.getcwd()
        open_process_namespaces('self', self.host_ns_fds,
                                self.namespaces)
        open_process_namespaces(self.pid, self.container_ns_fds,
                                self.namespaces)

    def attach(self):
        # Disable logging just to be sure log rotation does not happen in
        # the container.
        logging.disable(logging.CRITICAL)
        attach_to_process_namespaces(self.container_ns_fds, self.namespaces)

    def detach(self):
        try:
            # Re-attach to the process original namespaces.
            attach_to_process_namespaces(self.host_ns_fds,
                                         self.namespaces)
            # We are now in host context
            os.chdir(self.host_cwd)
            close_process_namespaces(self.container_ns_fds,
                                     self.namespaces)
            close_process_namespaces(self.host_ns_fds, self.namespaces)
        finally:
            # Enable logging again
            logging.disable(logging.NOTSET)


def run_as_another_namespace(
    pid,
    namespaces,
    function,
    *args,
    **kwargs
):
    hack_to_pre_load_modules()

    _args = (pid, namespaces, function)
    _kwargs = {'_args': tuple(args), '_kwargs': dict(kwargs)}
    return run_as_another_process(_run_as_another_namespace, _args, _kwargs)


def run_as_another_process(function, _args=(), _kwargs={}):
    try:
        queue = multiprocessing.Queue(2 ** 15)
    except OSError:
        # try again with a smaller queue
        queue = multiprocessing.Queue(2 ** 14)

    child_process = multiprocessing.Process(
        target=_function_wrapper,
        args=(queue, function),
        kwargs={'_args': _args, '_kwargs': _kwargs})
    child_process.start()

    child_exception, result = None, None
    try:
        (result, child_exception) = queue.get(timeout=IN_PROCESS_TIMEOUT)
    except Queue.Empty:
        child_exception = CrawlTimeoutError()
    except Exception as exc:
        logger.warn(exc)

    child_process.join(IN_PROCESS_TIMEOUT)

    # The join failed and the process might still be alive

    if child_process.is_alive():
        errmsg = ('Timed out waiting for process %d to exit.' %
                  child_process.pid)
        queue.close()
        os.kill(child_process.pid, 9)
        logger.error(errmsg)
        raise CrawlTimeoutError(errmsg)

    if result is None:
        if child_exception:
            raise child_exception
        raise CrawlError('Unknown crawl error.')
    return result


def _function_wrapper(
    queue,
    function,
    _args=(),
    _kwargs={}
):
    """
    Function to be used by run_as_another_process to wrap `function`
    and call it with _args and _kwargs. `queue` is used to get the result
    and any exception raised.
    :param queue:
    :param function:
    :param _args:
    :param _kwargs:
    :return:
    """

    # Die if the parent dies
    PR_SET_PDEATHSIG = 1
    get_libc().prctl(PR_SET_PDEATHSIG, signal.SIGHUP)

    def signal_handler_sighup(*args):
        logger.warning('Crawler parent process died, so exiting... Bye!')
        queue.close()
        exit(1)

    signal.signal(signal.SIGHUP, signal_handler_sighup)

    try:
        result = function(*_args, **_kwargs)

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


def _run_as_another_namespace(
        pid,
        namespaces,
        function,
        _args=(),
        _kwargs={}
):

    # os.closerange(1, 1000)
    context = ProcessContext(pid, namespaces)
    context.attach()
    try:
        return run_as_another_process(function, _args, _kwargs)
    finally:
        context.detach()


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
        ns_path = os.path.join('/proc', pid, 'ns', ct_ns)
        # arg 0 means readonly
        namespace_fd[ct_ns] = get_libc().open(ns_path, 0)
        if namespace_fd[ct_ns] == -1:
            errno_msg = get_errno_msg()
            error_msg = 'Opening the %s namespace file failed: %s' \
                % (ct_ns, errno_msg)
            logger.warning(error_msg)
            raise NamespaceFailedSetns(error_msg)


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
            if ct_ns == 'user':
                continue
            raise NamespaceFailedSetns(error_msg)
