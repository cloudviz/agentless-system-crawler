from collections import namedtuple


TomcatJVMFeature = namedtuple('TomcatJVMFeature', [
                              'free',
                              'total',
                              'max'
                              ])

TomcatMemoryFeature = namedtuple('TomcatMemoryFeature', [
                                 'name',
                                 'type',
                                 'initial',
                                 'committed',
                                 'maximum',
                                 'used'
                                 ])

TomcatConnectorFeature = namedtuple('TomcatConnectorFeature', [
                                    'connector',
                                    'maxThread',
                                    'currentThread',
                                    'currentThreadBusy',
                                    'requestMaxTime',
                                    'processingTime',
                                    'requestCount',
                                    'errorCount',
                                    'byteReceived',
                                    'byteSent'
                                    ])

TomcatWorkerFeature = namedtuple('TomcatWorkerFeature', [
                                 'connector',
                                 'stage',
                                 'time',
                                 'byteSent',
                                 'byteReceived',
                                 'client',
                                 'vhost',
                                 'request'
                                 ])
