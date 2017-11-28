from collections import namedtuple

LibertyServletFeature = namedtuple('LibertyServletFeature', [
                                   'name',
                                   'appName',
                                   'reqCount',
                                   'responseMean',
                                   'responseMax',
                                   'responseMin'
                                   ])

LibertyJVMFeature = namedtuple('LibertyJVMFeature', [
                               'heap',
                               'freeMemory',
                               'usedMemory',
                               'processCPU',
                               'gcCount',
                               'gcTime',
                               'upTime'
                               ])

LibertyThreadFeature = namedtuple('LibertyThreadFeature', [
                                  'activeThreads',
                                  'poolSize',
                                  'poolName'
                                  ])

LibertySessionFeature = namedtuple('LibertySessionFeature', [
                                   'name',
                                   'createCount',
                                   'liveCount',
                                   'activeCount',
                                   'invalidatedCount',
                                   'invalidatedCountByTimeout',
                                   ])

LibertyMongoConnectionFeature = namedtuple('LibertyMongoConnectionFeature', [
                                           'checkedOutCount',
                                           'waitQueueSize',
                                           'maxSize',
                                           'minSize',
                                           'host',
                                           'port',
                                           'size',
                                           ])
