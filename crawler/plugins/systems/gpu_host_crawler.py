import logging
from icrawl_plugin import IHostCrawler

logger = logging.getLogger('crawlutils')
pynvml = None


class GPUHostCrawler(IHostCrawler):

    def get_feature(self):
        return 'gpu'

    def _init_nvml(self):
        try:
            global pynvml
            import pip
            pip.main(['install', '--quiet', 'nvidia-ml-py'])
            import pynvml as pynvml
            pynvml.nvmlInit()
            return 0
        except pynvml.NVMLError, err:
            logger.debug('Failed to initialize NVML: ', err)
            return -1

    def _shutdown_nvml(self):
        try:
            pynvml.nvmlShutdown()
        except pynvml.NVMLError, err:
            logger.debug('Failed to shutdown NVML: ', err)

    def crawl(self, **kwargs):
        logger.debug('Crawling GPU metrics for the host')
        return self._crawl_in_system()

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

        if self._init_nvml() == -1:
            return

        num_gpus = pynvml.nvmlDeviceGetCount()

        for gpuid in range(0, num_gpus):
            gpuhandle = pynvml.nvmlDeviceGetHandleByIndex(gpuid)
            temperature = pynvml.nvmlDeviceGetTemperature(
                gpuhandle, pynvml.NVML_TEMPERATURE_GPU)
            memory = pynvml.nvmlDeviceGetMemoryInfo(gpuhandle)
            mem_total = memory.total / 1024 / 1024
            mem_used = memory.used / 1024 / 1024
            mem_free = memory.free / 1024 / 1024
            power_draw = pynvml.nvmlDeviceGetPowerUsage(gpuhandle) / 1000
            power_limit = pynvml.nvmlDeviceGetEnforcedPowerLimit(
                gpuhandle) / 1000
            util = pynvml.nvmlDeviceGetUtilizationRates(gpuhandle)
            util_gpu = util.gpu
            util_mem = util.memory
            entry = {
                'utilization': {'gpu': util_gpu, 'memory': util_mem},
                'memory': {'total': mem_total, 'free': mem_free,
                           'used': mem_used},
                'temperature': temperature,
                'power': {'draw': power_draw, 'limit': power_limit}
            }
            key = 'gpu{}'.format(gpuid)

            if gpuid == num_gpus - 1:
                self._shutdown_nvml()

            yield (key, entry, 'gpu')

        return
