import logging
import ctypes
import platform
import os
import sys
import psutil
from icrawl_plugin import IHostCrawler
from utils.dockerutils import exec_dockerps
from utils.misc import get_host_ipaddr

logger = logging.getLogger('crawlutils')
pynvml = None


class GPUHostCrawler(IHostCrawler):

    def get_feature(self):
        return 'gpu'

    def _load_nvidia_lib(self):
        try:
            lib_dir = os.getcwd() + '/utils/nvidialib'
            if platform.architecture()[0] == '64bit':
                ctypes.cdll.LoadLibrary(
                    lib_dir + '/lib64/libnvidia-ml.so.375.66')
            else:
                ctypes.cdll.LoadLibrary(
                    lib_dir + '/lib/libnvidia-ml.so.375.66')
        except:
            logger.debug(sys.exc_info()[0])
            return -1

    def _init_nvml(self):
        if self._load_nvidia_lib() == -1:
            return -1

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

    def _get_children_pids(self, pid):
        try:
            p = psutil.Process(pid=pid)
            child_pids = [c.pid for c in p.children(recursive=True)]
            return child_pids
        except:
            logger.debug(sys.exc_info()[0])
            return []

    def _get_containerid_from_pid(self, pid):
        # possible race conditions / stale info
        for inspect in self.inspect_arr:
            state = inspect['State']
            cont_pid = int(state['Pid'])
            cont_child_pids = self._get_children_pids(cont_pid)
            if pid in cont_child_pids:
                labels = inspect['Config']['Labels']
                pod_ns = labels.get('io.kubernetes.pod.namespace', 'NA')
                pod_name = labels.get('io.kubernetes.pod.name', 'NA')
                training_id = labels.get('training_id', pod_name)
                name = "%s.%s"%(pod_ns, training_id)
                return name
        return 'NA'

    def _get_container_id(self, gpuhandle):
        cont_ids = []
        pids = []
        try:
            proc_objs = pynvml.nvmlDeviceGetComputeRunningProcesses(gpuhandle)
            if not proc_objs:
                return ['NA']
            for proc_obj in proc_objs:
                pids.append(proc_obj.pid)
            for pid in pids:
                cont_ids.append(self._get_containerid_from_pid(pid))
            return cont_ids
        except pynvml.NVMLError, err:
            logger.debug('Failed to get pid on gpu: ', err)

    def _get_feature_key(self, gpuhandle, gpuid):
        hostip = get_host_ipaddr().replace('.', '/')
        key = '{}.gpu{}'.format(hostip, gpuid)
        cont_ids = self._get_container_id(gpuhandle)
        for cont_id in cont_ids:
            key = key + '.' + cont_id
        return key

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

        self.inspect_arr = exec_dockerps()

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
            key = self._get_feature_key(gpuhandle, gpuid)
            if gpuid == num_gpus - 1:
                self._shutdown_nvml()

            yield (key, entry, 'gpu')

        return
