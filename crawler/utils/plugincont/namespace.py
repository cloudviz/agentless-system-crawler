#This namespace.py is needed for setns() in userns-remap world
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
import misc
import traceback
import time
from crawler_exceptions import CrawlTimeoutError, CrawlError

logger = logging.getLogger('crawlutils')

try:
    libc = ctypes.CDLL('libc.so.6')
except Exception as e:
    libc = None

ALL_NAMESPACES = [
    'user',
    'pid',
    'uts',
    'ipc',
    'net',
    'mnt',
]

IN_CONTAINER_TIMEOUT = 300

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

        self.container_ns_fds = {}
        try:
            open_process_namespaces(self.pid, self.container_ns_fds,
                                    self.namespaces)
        except Exception as e:
            logging.disable(logging.NOTSET)
            logger.debug(e)
            try:
                close_process_namespaces(self.host_ns_fds, self.namespaces)
            except Exception as e:
                logger.warning('Could not close the namespaces: %s' % e)
            raise

        try:
            attach_to_process_namespaces(self.container_ns_fds,
                                         self.namespaces)
        except Exception as e:
            logging.disable(logging.NOTSET)
            error_msg = ('Could not attach to a pid={pid} namespace, Exception: {exc}'.format(
                pid=self.pid, exc=e))
            logger.error(error_msg)
            raise

def run_as_another_namespace(
    pid,
    namespaces,
    function,
    *args,
    **kwargs
):

    # Create the queue and its pipes before attaching to the container mnt namespace
    queue = multiprocessing.Queue(2 ** 15)

    context = ProcessContext(pid, namespaces)

    # Fork before attaching to the container mnt namespace to drop to a single thread
    child_process = multiprocessing.Process(target=_run_as_another_namespace_executor,
                                            args=(queue, context, pid, function, args),
                                            kwargs=kwargs)
    child_process.start()

    grandchild_exception = None
    try:
        (result, grandchild_exception) = queue.get(timeout=IN_CONTAINER_TIMEOUT)
    except Queue.Empty:
        grandchild_exception = CrawlTimeoutError('Timed out waiting for response from crawler process')
    except Exception:
        result = None
    if grandchild_exception:
        result = None

    child_process.join(1)
    # If the join timed out the process might still be alive
    if child_process.is_alive():
        errmsg = ('Timed out waiting for process %d to exit.' %
                  child_process.pid)
        queue.close()
        os.kill(child_process.pid, 9)
        logger.error(errmsg)
        raise CrawlTimeoutError(errmsg)

    if result is None:
        if grandchild_exception:
            raise grandchild_exception
        raise CrawlError('Unknown crawl error.')
    return result

def signal_handler_sighup(*args):
    logger.warning('Crawler parent process died, so exiting... Bye!')
    exit(1)

def cache_modules_from_crawler_mnt_namespace():
    prime_process = multiprocessing.Process(target=time.sleep, args=(1,))
    prime_process.start()
    prime_process.is_alive()
    prime_process.join(0.001)
    prime_process.terminate()
    prime_process.join()
    prime_process.is_alive()
    del prime_process
    prime_queue = multiprocessing.Queue(2 ** 15)
    prime_queue.put('something')
    prime_queue.get()
    prime_queue.close()
    prime_queue.join_thread()
    del prime_queue

def wait_for_linux_thread_cleanup(expected_threads):
    start_time = os.times()[4]
    while True:
        task_count = len(os.listdir('/proc/{}/task'.format(os.getpid())))
        if task_count > expected_threads:
            time.sleep(0.001)
        else:
            break
    logger.debug('Waited {} seconds for Linux to cleanup terminated threads'.format(os.times()[4] - start_time))

def _run_as_another_namespace_executor(queue, context, pid, function, args, **kwargs):
    # Die if the parent dies
    PR_SET_PDEATHSIG = 1
    libc.prctl(PR_SET_PDEATHSIG, signal.SIGHUP)
    signal.signal(signal.SIGHUP, signal_handler_sighup)

    cache_modules_from_crawler_mnt_namespace()
    wait_for_linux_thread_cleanup(1)
    try:
        context.attach()
    except Exception as e:
        queue.put((None, e))
        sys.exit(1)

    try:
        grandchild_process = multiprocessing.Process(
            name='crawler-%s' % pid,
            target=function_wrapper,
            args=(queue, function, args),
            kwargs=kwargs)
        grandchild_process.start()
    except OSError:
        sys.exit(1)

    grandchild_process.join(IN_CONTAINER_TIMEOUT)
    # If the join timed out the process might still be alive
    if grandchild_process.is_alive():
        os.kill(grandchild_process.pid, 9)
        sys.exit(1)

def function_wrapper(
    queue,
    function,
    *args,
    **kwargs
):

    # Die if the parent dies
    PR_SET_PDEATHSIG = 1
    libc.prctl(PR_SET_PDEATHSIG, signal.SIGHUP)
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
        e.traceback = traceback.format_exc()
        queue.put((None, e))
        queue.close()
        sys.exit(1)

def open_process_namespaces(pid, namespace_fd, namespaces):
    for ct_ns in namespaces:
        try:

            # arg 0 means readonly
            namespace_fd[ct_ns] = libc.open('/proc/' + str(pid) + '/ns/' + ct_ns, 0)
            if namespace_fd[ct_ns] == -1:
                errno_msg = get_errno_msg(libc)
                error_msg = 'Opening the %s namespace file failed: %s' % (ct_ns, errno_msg)
                logger.warning(error_msg)
                raise OSError('Failed to open {ns} namespace of {pid}: {err}'.format(ns=ct_ns, pid=pid, err=error_msg))
        except Exception as e:
            error_msg = 'The open() syscall failed with: %s' % e
            logger.warning(error_msg)
            raise

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
                errno_msg = get_errno_msg(libc)
                error_msg = ('Could not attach to the container %s '
                             'namespace (fd=%s): %s' %
                             (ct_ns, namespace_fd[ct_ns], errno_msg))
                logger.warning(error_msg)
                raise OSError('Failed to attach to {ns} namespace of {fd}: {err}'.format(ns=ct_ns, fd=namespace_fd[ct_ns], err=error_msg))
        except Exception as e:
            error_msg = 'The setns() syscall failed with: %s' % e
            logger.warning(error_msg)
            logger.exception(e)
            raise

def get_errno_msg(libc):
    try:
        import ctypes
        libc.__errno_location.restype = ctypes.POINTER(ctypes.c_int)
        errno = libc.__errno_location().contents.value
        errno_msg = os.strerror(errno)
        return errno_msg
    except Exception:
        return 'unknown error'            
