try:
    from crawler.icrawl_plugin import IVMCrawler
    # XXX: make crawler agnostic of this
    from crawler.features import MemoryFeature
except ImportError:
    from icrawl_plugin import IVMCrawler
    # XXX: make crawler agnostic of this
    from features import MemoryFeature
import logging

try:
    import psvmi
except ImportError:
    psvmi = None

logger = logging.getLogger('crawlutils')


class MemoryVmCrawler(IVMCrawler):

    def get_feature(self):
        return 'memory'

    def crawl(self, vm_desc, **kwargs):
        if psvmi is None:
            raise NotImplementedError()
        else:
            (domain_name, kernel_version, distro, arch) = vm_desc
            # XXX: this has to be read from some cache instead of
            # instead of once per plugin/feature
            vm_context = psvmi.context_init(
                domain_name, domain_name, kernel_version, distro, arch)

            sysmem = psvmi.system_memory_info(vm_context)
            feature_attributes = MemoryFeature(
                sysmem.memory_used,
                sysmem.memory_buffered,
                sysmem.memory_cached,
                sysmem.memory_free,
                (sysmem.memory_used * 100 / (sysmem.memory_used +
                                             sysmem.memory_free)))
            return [('memory', feature_attributes, 'memory')]
