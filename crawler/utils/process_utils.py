
import fcntl
import os
import signal
import struct
import subprocess

_SC_OPEN_MAX = 4


# Flake 8's complexity 10 limit requires odd code changes; so skip
# its QA here
# flake8: noqa


def _close_fds(keep_fds, max_close_fd=None):
    """
      Have a process close all file descriptors except for stderr, stdout,
      and stdin and those ones in the keep_fds list
      The maximum file descriptor to close can be provided to avoid long
      delays; this max_fd value depends on the program being used and could
      be a low number if the program does not have many file descriptors
    """
    maxfd = os.sysconf(_SC_OPEN_MAX)
    if max_close_fd:
        maxfd = min(maxfd, max_close_fd)

    for fd in range(3, maxfd):
        if fd in keep_fds:
            continue
        try:
            os.close(fd)
        except:
            pass


def start_child(params, pass_fds, null_fds, ign_sigs, setsid=False,
                max_close_fd=None, **kwargs):
    """
      Start a child process without leaking file descriptors of the
      current process. We pass a list of file descriptors to the
      child process and close all other ones. We redirect a list of
      null_fds (typically stderr, stdout, stdin) to /dev/null.

      This function is a wrapper for subprocess.Popen().

      @params: start the process with the given parameters.
      @pass_fds: a list of file descriptors to pass to the child process
                 close all file descriptors not in this list starting
                 at file descriptor '3'.
      @null_fds: a list of file descriptors to redirect to /dev/null;
                 a typical list here would be 0, 1, and 2 for
                 stdin, stdout, and stderr
      @ign_sigs: a list of signals to ignore
      @set_sid:  whether to call os.setsid()
      @max_close_fd: max. number of file descriptors to close;
                     can be a low number in case program doesn't
                     typically have many open file descriptors;
      @**kwargs: kwargs to pass to subprocess.Popen()

      This function returns the process ID of the process that
      was started and an error code. In case of success the process
      ID is a positive number, -1 otherwise. The error code indicates
      the errno returned from subprocess.Popen()

    """
    rfd, wfd = os.pipe()

    try:
        pid = os.fork()
    except OSError as err:
        os.close(rfd)
        os.close(wfd)
        return -1, err.errno

    if pid == 0:
        # child
        os.close(rfd)
        flags = fcntl.fcntl(wfd, fcntl.F_GETFD)
        fcntl.fcntl(wfd, fcntl.F_SETFD, flags | fcntl.FD_CLOEXEC)

        if len(null_fds):
            nullfd = os.open('/dev/null', os.O_RDWR)
            for fd in null_fds:
                os.dup2(nullfd, fd)
            os.close(nullfd)

        keep_fds = pass_fds
        keep_fds.extend(null_fds)
        keep_fds.append(wfd)

        _close_fds(keep_fds, max_close_fd=max_close_fd)

        for ign_sig in ign_sigs:
            signal.signal(ign_sig, signal.SIG_IGN)
        if setsid:
            os.setsid()

        errcode = 0
        pid = -1

        try:
            process = subprocess.Popen(params, **kwargs)
            pid = process.pid
        except OSError as err:
            errcode = err.errno

        data = struct.pack('ii', pid, errcode)
        os.write(wfd, data)

        os._exit(0)
    else:
        os.close(wfd)

        try:
            message = os.read(rfd, 8)
            pid, errcode, = struct.unpack('ii', message)
        except:
            pid = -1
        os.close(rfd)
        # wait for child process to _exit()
        os.waitpid(-1, 0)

        return pid, errcode
