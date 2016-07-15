#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import multiprocessing
import Queue
import logging
import sys
import types
import signal
from ctypes import CDLL
# import cPickle as pickle
import misc
from crawler_exceptions import CrawlTimeoutError, CrawlError

logger = logging.getLogger('crawlutils')

try:
    libc = CDLL('libc.so.6')
except Exception as e:
    logger.warning('Can not crawl containers as there is no libc: %s' % e)
    raise e

ALL_NAMESPACES = 'user pid uts ipc net mnt'.split()
IN_CONTAINER_TIMEOUT = 30


def get_pid_namespace(pid):
    try:
        ns = os.stat('/proc/' + str(pid) + '/ns/pid').st_ino
        return ns
    except Exception:
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

        try:
            os.chdir(self.host_cwd)
        except Exception as e:
            logger.error('Could not move to the host cwd: %s' % e)
            raise
        logging.disable(logging.NOTSET)
        try:
            close_process_namespaces(self.container_ns_fds,
                                     self.namespaces)
            close_process_namespaces(self.host_ns_fds, self.namespaces)
        except Exception as e:
            logger.warning('Could not close the namespaces: %s' % e)


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
    queue = multiprocessing.Queue(2 ** 15)

    try:
        child_process = multiprocessing.Process(
            name='crawler-%s' %
            pid, target=function_wrapper, args=(
                queue, function, args), kwargs=kwargs)
        child_process.start()
    except OSError:
        queue.close()
        raise CrawlError()

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
    libc.prctl(PR_SET_PDEATHSIG, signal.SIGHUP)

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
    p.join()
    queue.get()


def open_process_namespaces(pid, namespace_fd, namespaces):
    for ct_ns in namespaces:
        try:

            # arg 0 means readonly

            namespace_fd[ct_ns] = libc.open('/proc/' + pid + '/ns/' +
                                            ct_ns, 0)
            if namespace_fd[ct_ns] == -1:
                errno_msg = misc.get_errno_msg(libc)
                error_msg = 'Opening the %s namespace file failed: %s' \
                    % (ct_ns, errno_msg)
                logger.warning(error_msg)
                if ct_ns == 'mnt':
                    raise Exception(error_msg)
        except Exception as e:
            error_msg = 'The open() syscall failed with: %s' % e
            logger.warning(error_msg)
            if ct_ns == 'mnt':
                raise e


def close_process_namespaces(namespace_fd, namespaces):
    for ct_ns in namespaces:
        try:
            libc.close(namespace_fd[ct_ns])
        except Exception as e:
            error_msg = 'The close() syscall failed with: %s' % e
            logger.warning(error_msg)


def attach_to_process_namespaces(namespace_fd, ct_namespaces):
    for ct_ns in ct_namespaces:
        try:
            if hasattr(libc, 'setns'):
                r = libc.setns(namespace_fd[ct_ns], 0)
            else:
                # The Linux kernel ABI should be stable enough
                __NR_setns = 308
                r = libc.syscall(__NR_setns, namespace_fd[ct_ns], 0)
            if r == -1:
                errno_msg = misc.get_errno_msg(libc)
                error_msg = ('Could not attach to the container %s '
                             'namespace (fd=%s): %s' %
                             (ct_ns, namespace_fd[ct_ns], errno_msg))
                logger.warning(error_msg)
                if ct_ns == 'mnt':
                    raise Exception(error_msg)
        except Exception as e:
            error_msg = 'The setns() syscall failed with: %s' % e
            logger.warning(error_msg)
            if ct_ns == 'mnt':
                logger.exception(e)
                raise e
