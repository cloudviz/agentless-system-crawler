try:
    from crawler.features import CpuFeature
    from crawler.icrawl_plugin import IHostCrawler
except ImportError:
    from features import CpuFeature
    from icrawl_plugin import IHostCrawler

import logging
import psutil

logger = logging.getLogger('crawlutils')


class CpuHostCrawler(IHostCrawler):

    def get_feature(self):
        return 'cpu'

    def crawl(self, **kwargs):
        logger.debug('Crawling %s' % (self.get_feature()))

        for (idx, cpu) in enumerate(psutil.cpu_times_percent(percpu=True)):
            feature_attributes = CpuFeature(
                cpu.idle,
                cpu.nice,
                cpu.user,
                cpu.iowait,
                cpu.system,
                cpu.irq,
                cpu.steal,
                100 - int(cpu.idle),
            )
            feature_key = '{0}-{1}'.format('cpu', idx)
            yield (feature_key, feature_attributes, 'cpu')
