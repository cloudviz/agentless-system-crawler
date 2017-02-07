from collections import namedtuple


def get_feature(stats):
    feature_attributes = ApacheFeature(
        stats['BusyWorkers'],
        stats['IdleWorkers'],
        stats['waiting_for_connection'],
        stats['starting_up'],
        stats['reading_request'],
        stats['sending_reply'],
        stats['keepalive_read'],
        stats['dns_lookup'],
        stats['closing_connection'],
        stats['logging'],
        stats['graceful_finishing'],
        stats['idle_worker_cleanup'],
        stats['BytesPerSec'],
        stats['BytesPerReq'],
        stats['ReqPerSec'],
        stats['Uptime'],
        stats['Total_kBytes'],
        stats['Total_Accesses']
    )
    return feature_attributes

ApacheFeature = namedtuple('ApacheFeature', [
    'BusyWorkers',
    'IdleWorkers',
    'waiting_for_connection',
    'starting_up',
    'reading_request',
    'sending_reply',
    'keepalive_read',
    'dns_lookup',
    'closing_connection',
    'logging',
    'graceful_finishing',
    'idle_worker_cleanup',
    'BytesPerSec',
    'BytesPerReq',
    'ReqPerSec',
    'Uptime',
    'Total_kBytes',
    'Total_Accesses'
])
