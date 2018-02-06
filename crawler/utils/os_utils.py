import logging
import platform
import time

import psutil

import utils.misc
from utils import osinfo
from utils.features import OSFeature

logger = logging.getLogger('crawlutils')


def crawl_os():
    feature_key = platform.system().lower()
    try:
        os_kernel = platform.platform()
    except:
        os_kernel = 'unknown'

    result = osinfo.get_osinfo(mount_point='/')
    os_distro = result['os'] if 'os' in result else 'unknown'
    os_version = result['version'] if 'version' in result else 'unknown'

    ips = utils.misc.get_host_ip4_addresses()

    boot_time = psutil.boot_time()
    uptime = int(time.time()) - boot_time
    feature_attributes = OSFeature(
        boot_time,
        uptime,
        ips,
        os_distro,
        os_version,
        os_kernel,
        platform.machine()
    )

    return [(feature_key, feature_attributes, 'os')]


def crawl_os_mountpoint(mountpoint='/'):
    result = osinfo.get_osinfo(mount_point=mountpoint)
    os_distro = result['os'] if 'os' in result else 'unknown'
    os_version = result['version'] if 'version' in result else 'unknown'

    feature_key = 'linux'
    feature_attributes = OSFeature(  # boot time unknown for img
                                     # live IP unknown for img
        'unsupported',
        'unsupported',
        '0.0.0.0',
        os_distro,
        os_version,
        'unknown',
        'unknown'
    )
    return [(feature_key, feature_attributes, 'os')]
