import logging

import psutil

from icrawl_plugin import IVMCrawler
from utils.connection_utils import crawl_single_connection

try:
    import psvmi
except ImportError:
    psvmi = None

logger = logging.getLogger('crawlutils')


class ConnectionVmCrawler(IVMCrawler):

    def get_feature(self):
        return 'connection'

    def crawl(self, vm_desc, **kwargs):
        created_since = -1

        if psvmi is None:
            raise NotImplementedError()
        else:
            (domain_name, kernel_version, distro, arch) = vm_desc
            # XXX: this has to be read from some cache instead of
            # instead of once per plugin/feature
            vm_context = psvmi.context_init(
                domain_name, domain_name, kernel_version, distro, arch)
            proc_list = psvmi.process_iter(vm_context)

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
