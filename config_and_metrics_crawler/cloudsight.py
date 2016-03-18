#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import json
import logging

logger = logging.getLogger('crawlutils')

def get_namespace(long_id, options):
    assert type(long_id) is str or unicode, "long_id is not a string"
    assert 'name' in options and 'host_namespace' in options
    name = options['name']
    name = (name if len(name) > 0 else long_id[:12])
    name = (name[1:] if name[0] == '/' else name)
    return options['host_namespace'] + '/' + name

def get_log_file_list(long_id, options):
    assert type(long_id) is str or unicode, "long_id is not a string"
    assert 'container_logs' in options
    container_logs = options['container_logs']
    for log in container_logs:
        name = log['name']
        if not os.path.isabs(name) or '..' in name:
            container_logs.remove(log)
            logger.warning(
                'User provided a log file path that is not absolute: %s' %
                name)
    return container_logs

def get_container_log_prefix(long_id, options):
    assert type(long_id) is str or unicode, "long_id is not a string"
    return get_namespace(long_id, options)
