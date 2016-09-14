import platform
import dockerutils

# Additional modules

import osinfo

# External dependencies that must be pip install'ed separately

import psutil
import misc
import time


from icrawl_plugin import IContainerCrawler
from features import OSFeature
from namespace import run_as_another_namespace, ALL_NAMESPACES


class OSContainerCrawler(IContainerCrawler):

    def get_feature(self):
        return 'os'

    def crawl(self, container_id):
        inspect = dockerutils.exec_dockerinspect(container_id)
        state = inspect['State']
        pid = str(state['Pid'])
        return run_as_another_namespace(pid,
                                        ALL_NAMESPACES,
                                        self._crawl_in_system)

        # XXX consider moving this mode of crawling (without setns) to another
        # plugin.
        # return _crawl_without_setns(container_id)

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
