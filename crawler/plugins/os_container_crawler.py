import platform
import misc
import time
import osinfo
import dockerutils
from icrawl_plugin import IContainerCrawler
from features import OSFeature
from namespace import run_as_another_namespace, ALL_NAMESPACES
import logging

# External dependencies that must be pip install'ed separately

import psutil

logger = logging.getLogger('crawlutils')


class OSContainerCrawler(IContainerCrawler):

    def get_feature(self):
        return 'os'

    def crawl(self, container_id, avoid_setns=False, **kwargs):
        inspect = dockerutils.exec_dockerinspect(container_id)
        state = inspect['State']
        pid = str(state['Pid'])
        logger.debug('Crawling OS for container %s' % container_id)

        if avoid_setns:
            return self._crawl_without_setns(container_id)
        else:  # in all other cases, including wrong mode set
            return run_as_another_namespace(pid,
                                            ALL_NAMESPACES,
                                            self._crawl_in_system)

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

    def _crawl_without_setns(self, container_id):
        mountpoint = dockerutils.get_docker_container_rootfs_path(container_id)

        result = osinfo.get_osinfo(mount_point=mountpoint)
        if result:
            os_distro = result['os']
            os_version = result['version']
        else:
            os_distro = 'unknown'
            os_version = 'unknown'

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
