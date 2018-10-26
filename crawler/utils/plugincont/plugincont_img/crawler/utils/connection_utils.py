import psutil

from utils.features import ConnectionFeature


def crawl_connections():
    created_since = -1

    proc_list = psutil.process_iter()

    for p in proc_list:
        pid = (p.pid() if hasattr(p.pid, '__call__') else p.pid)
        status = (p.status() if hasattr(p.status, '__call__'
                                        ) else p.status)
        if status == psutil.STATUS_ZOMBIE:
            continue

        create_time = (
            p.create_time() if hasattr(
                p.create_time,
                '__call__') else p.create_time)
        name = (p.name() if hasattr(p.name, '__call__') else p.name)

        if create_time <= created_since:
            continue
        for conn in p.get_connections():
            yield crawl_single_connection(conn, pid, name)


def crawl_single_connection(c, pid, name):
    """Returns a ConnectionFeature"""
    try:
        (localipaddr, localport) = c.laddr[:]
    except:

        # Older version of psutil uses local_address instead of
        # laddr.

        (localipaddr, localport) = c.local_address[:]
    try:
        if c.raddr:
            (remoteipaddr, remoteport) = c.raddr[:]
        else:
            (remoteipaddr, remoteport) = (None, None)
    except:

        # Older version of psutil uses remote_address instead
        # of raddr.

        if c.remote_address:
            (remoteipaddr, remoteport) = \
                c.remote_address[:]
        else:
            (remoteipaddr, remoteport) = (None, None)
    feature_key = '{0}/{1}/{2}'.format(pid,
                                       localipaddr, localport)
    return (feature_key, ConnectionFeature(
        localipaddr,
        localport,
        name,
        pid,
        remoteipaddr,
        remoteport,
        str(c.status),
    ), 'connection')
