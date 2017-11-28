from collections import namedtuple


def get_feature(match1, match2, match3):
    feature_attributes = NginxFeature(
        int(match1.group(1)),
        int(match2.group(1)),
        int(match2.group(3)),
        int(match3.group(1)),
        int(match3.group(2)),
        int(match3.group(3))
    )
    return feature_attributes

NginxFeature = namedtuple('NginxFeature', [
    'Connections',
    'Accepted',
    'Requests',
    'Reading',
    'Writing',
    'Waiting'
])
