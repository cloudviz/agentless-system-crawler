import logging
import os
import subprocess
from icrawl_plugin import IHostCrawler

logger = logging.getLogger('crawlutils')

NVIDIA_SMI = "/usr/bin/nvidia-smi"


class GPUHostCrawler(IHostCrawler):

    def get_feature(self):
        return 'gpu'

    def crawl(self, **kwargs):
        logger.debug('Crawling GPU metrics for the host')
        self._crawl_in_system()

    def _crawl_in_system(self):
        '''
        nvidia-smi returns following: MEMORY, UTILIZATION, ECC, TEMPERATURE,
        POWER, CLOCK, COMPUTE, PIDS, PERFORMANCE, SUPPORTED_CLOCKS,
        PAGE_RETIREMENT, ACCOUNTING

        currently, following are requested based on dlaas requirements:
            utilization.gpu, utilization.memory,
            memory.total, memory.free, memory.used
        nvidia-smi --query-gpu=utilization.gpu,utilization.memory,\
            memory.total,memory.free,memory.used --format=csv,noheader,nounits
        '''

        if not os.path.exists(NVIDIA_SMI):
            return

        params = ['utilization.gpu', 'utilization.memory', 'memory.total',
                  'memory.free', 'memory.used', 'temperature.gpu',
                  'power.draw', 'power.limit']

        nvidia_smi_proc = subprocess.Popen(
            [NVIDIA_SMI, '--query-gpu={}'.format(','.join(params)),
                '--format=csv,noheader,nounits'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        nvidia_smi_proc_out, err = nvidia_smi_proc.communicate()

        if nvidia_smi_proc.returncode > 0:
            raise Exception('Unable to get gpu metrics')

        metrics = nvidia_smi_proc_out.split('\n')
        for i, val_str in enumerate(metrics):
            if len(val_str) != 0:
                values = val_str.split(',')
                entry = {
                    'utilization': {'gpu': values[0], 'memory': values[1]},
                    'memory': {'total': values[2], 'free': values[3],
                               'used': values[4]},
                    'temperature': values[5],
                    'power': {'draw': values[6], 'limit': values[7]}
                }
                key = 'gpu{}'.format(i)
                yield (key, entry)
        return
