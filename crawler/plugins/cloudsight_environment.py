#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import json
import logging
import copy

try:
    from crawler.runtime_environment import IRuntimeEnvironment
except ImportError:
    from runtime_environment import IRuntimeEnvironment

logger = logging.getLogger('crawlutils')

class CloudsightEnvironment(IRuntimeEnvironment):
    name = 'cloudsight'

    def get_environment_name(self):
        return self.name

    def get_container_namespace(self, long_id, options):
	assert type(long_id) is str or unicode, "long_id is not a string"
	assert 'name' in options and 'host_namespace' in options
	name = options['name']
	name = (name if len(name) > 0 else long_id[:12])
	name = (name[1:] if name[0] == '/' else name)
	return options['host_namespace'] + '/' + name

    def get_container_log_file_list(self, long_id, options):
	assert type(long_id) is str or unicode, "long_id is not a string"
	assert 'container_logs' in options
	container_logs = copy.deepcopy(options['container_logs'])
	for log in container_logs:
	    name = log['name']
	    if not os.path.isabs(name) or '..' in name:
		container_logs.remove(log)
		logger.warning(
		    'User provided a log file path that is not absolute: %s' %
		    name)
	return container_logs

    def get_container_log_prefix(self, long_id, options):
	assert type(long_id) is str or unicode, "long_id is not a string"
	return self.get_container_namespace(long_id, options)
