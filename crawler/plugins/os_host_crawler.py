import platform
import misc
import time
import osinfo
from icrawl_plugin import IHostCrawler
from features import OSFeature
import logging

# External dependencies that must be pip install'ed separately

import psutil

logger = logging.getLogger('crawlutils')


class OSHostCrawler(IHostCrawler):

    def get_feature(self):
        return 'os'

    def crawl(self, **kwargs):
        return self._crawl_in_system()

    def _crawl_in_system(self):
        feature_key = platform.system().lower()
        try:
            os_kernel = platform.platform()
        except:
            os_kernel = 'unknown'

        result = osinfo.get_osinfo(mount_point='/')
        if result:
            os_distro = result['os']
            os_version = result['version']
        else:
            os_distro = 'unknown'
            os_version = 'unknown'

        ips = misc.get_host_ip4_addresses()

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
