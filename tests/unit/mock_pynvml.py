#class pynvml()
import collections

Memory = collections.namedtuple('Memory', 'total used free')
Utilization = collections.namedtuple('Utilization', 'gpu memory')

NVML_TEMPERATURE_GPU = 0

def nvmlInit():
    pass

def nvmlShutdown():
    pass

def nvmlDeviceGetCount():
    return 1

def nvmlDeviceGetHandleByIndex(arg):
    return 0

def nvmlDeviceGetTemperature(arg1, arg2):
    return 31

def nvmlDeviceGetMemoryInfo(arg):
    retVal = 12205 * 1024 * 1024
    return Memory(total=retVal, used=0, free=retVal)

def nvmlDeviceGetPowerUsage(arg):
    return 27000

def nvmlDeviceGetEnforcedPowerLimit(arg):
    return 149000

def nvmlDeviceGetUtilizationRates(arg):
    return Utilization(gpu=0, memory=0)



