import json
import time
from morph import flatten


def write_in_csv_format(iostream, frame):
    """
    Writes frame data and metadata into iostream in csv format.

    :param iostream: a CStringIO used to buffer the formatted features.
    :param frame: a BaseFrame object to be written into iostream
    :return: None
    """
    iostream.write('%s\t%s\t%s\n' %
                   ('metadata', json.dumps('metadata'),
                    json.dumps(frame.metadata, separators=(',', ':'))))
    for (key, val, feature_type) in frame.data:
        if not isinstance(val, dict):
            val = val._asdict()
        iostream.write('%s\t%s\t%s\n' % (
            feature_type, json.dumps(key),
            json.dumps(val, separators=(',', ':'))))


def write_in_json_format(iostream, frame):
    """
    Writes frame data and metadata into iostream in json format.

    :param iostream: a CStringIO used to buffer the formatted features.
    :param frame: a BaseFrame object to be written into iostream
    :return: None
    """
    iostream.write('%s\n' % json.dumps(frame.metadata))
    for (key, val, feature_type) in frame.data:
        if not isinstance(val, dict):
            val = val._asdict()
        val['feature_type'] = feature_type
        val['namespace'] = frame.metadata.get('namespace', '')
        iostream.write('%s\n' % json.dumps(val))


def write_in_logstash_format(iostream, frame):
    """
    Writes frame data and meta data in json format.
    Similar to write_in_json_format, but this method concatenate them
    in to a single json object.

    :param iostream: a CStringIO used to buffer the formatted features.
    :param frame: a BaseFrame Object to be written into iostream
    :return: None
    """
    payload = {}
    payload['metadata'] = frame.metadata
    for (key, val, feature_type) in frame.data:
        if not isinstance(val, dict):
            val = val._asdict()
        if feature_type not in payload:
            payload[feature_type] = {}
        payload[feature_type][key] = val
    iostream.write('%s\n' % json.dumps(payload))


def write_in_graphite_format(iostream, frame):
    """
    Writes frame data and metadata into iostream in graphite format.

    :param iostream: a CStringIO used to buffer the formatted features.
    :param frame: a BaseFrame object to be written into iostream
    :return: None
    """
    namespace = frame.metadata.get('namespace', '')
    for (key, val, feature_type) in frame.data:
        if not isinstance(val, dict):
            val = val._asdict()
        write_feature_in_graphite_format(iostream, namespace,
                                         key, val, feature_type)


def write_feature_in_graphite_format(iostream, namespace,
                                     feature_key, feature_val,
                                     feature_type):
    """
    Write a feature in graphite format into iostream. The graphite format
    looks like this, one line per metric value:

        [namespace].[feature_key].[metric] [value] [timestamp]\r\n
        [namespace].[feature_key].[metric] [value] [timestamp]\r\n
        [namespace].[feature_key].[metric] [value] [timestamp]\r\n

    This function converts a feature into that string and writes it into
    the iostream.

    :param namespace: Frame namespace for this feature
    :param feature_type:
    :param feature_key:
    :param feature_val:
    :param iostream: a CStringIO used to buffer the formatted features.
    :return: None
    """
    timestamp = time.time()
    items = flatten(feature_val).items()
    if isinstance(namespace, dict):
        namespace = json.dumps(namespace)
    else:
        namespace = namespace.replace('/', '.')

    for (metric, value) in items:
        try:
            # Only emit values that we can cast as floats
            value = float(value)
        except (TypeError, ValueError):
            continue

        metric = metric.replace('(', '_').replace(')', '')
        metric = metric.replace(' ', '_').replace('-', '_')
        metric = metric.replace('/', '_').replace('\\', '_')

        feature_key = feature_key.replace('_', '-')
        if 'cpu' in feature_key or 'memory' in feature_key:
            metric = metric.replace('_', '-')
        if 'if' in metric:
            metric = metric.replace('_tx', '.tx')
            metric = metric.replace('_rx', '.rx')
        if feature_key == 'load':
            feature_key = 'load.load'
        feature_key = feature_key.replace('/', '$')

        tmp_message = '%s.%s.%s %f %d\r\n' % (namespace, feature_key,
                                              metric, value, timestamp)
        iostream.write(tmp_message)
