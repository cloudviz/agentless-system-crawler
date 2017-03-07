import ctypes.util
import errno
import os
import socket

libc = ctypes.CDLL(ctypes.util.find_library('c'))


def if_indextoname(ifindex):
    libc.if_indextoname.argtypes = [ctypes.c_uint32, ctypes.c_char_p]
    libc.if_indextoname.restype = ctypes.c_char_p

    ifname = ctypes.create_string_buffer(16)
    ifname = libc.if_indextoname(ifindex, ifname)
    if not ifname:
        err = errno.ENXIO
        raise OSError(err, os.strerror(err))
    return ifname


def open_udp_port(bindaddr, min, max):
    """
      Try to open a UDP listening port in the given range
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for port in range(min, max + 1):
        try:
            sock.bind((bindaddr, port))
            return sock, port
        except:
            pass

    sock.close()
    return None, None
