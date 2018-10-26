import logging

import psutil

from icrawl_plugin import IHostCrawler
from utils.features import CpuFeature

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
