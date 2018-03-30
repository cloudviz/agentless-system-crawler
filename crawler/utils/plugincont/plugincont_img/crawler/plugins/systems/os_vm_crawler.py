import logging

from icrawl_plugin import IVMCrawler
from utils.features import OSFeature

# External dependencies that must be pip install'ed separately

try:
    import psvmi
except ImportError:
    psvmi = None

logger = logging.getLogger('crawlutils')


class os_vm_crawler(IVMCrawler):

    def get_feature(self):
        return 'os'

    def crawl(self, vm_desc, **kwargs):
        if psvmi is None:
            raise NotImplementedError()
        else:
            (domain_name, kernel_version, distro, arch) = vm_desc
            # XXX: not good, context_init was being done once per VM
            # in previous monolithic model, now it's once per plugin/feature
            vm_context = psvmi.context_init(
                domain_name, domain_name, kernel_version, distro, arch)
            sys = psvmi.system_info(vm_context)
            feature_attributes = OSFeature(
                sys.boottime,
                'unknown',
                sys.ipaddr,
                sys.ostype,
                sys.osversion,
                sys.osrelease,
                sys.osplatform
            )
            feature_key = sys.ostype
        return [(feature_key, feature_attributes, 'os')]
