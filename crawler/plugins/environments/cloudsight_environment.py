#!/usr/bin/env python
# -*- coding: utf-8 -*-

import copy
import logging
import os

from runtime_environment import IRuntimeEnvironment

try:
    unicode        # Python 2
except NameError:
    unicode = str  # Python 3

logger = logging.getLogger('crawlutils')


class CloudsightEnvironment(IRuntimeEnvironment):
    name = 'cloudsight'

    def get_environment_name(self):
        return self.name

    def get_container_namespace(self, long_id, options):
        assert isinstance(long_id, (str, unicode)), "long_id is not a string"
        assert 'name' in options and 'host_namespace' in options
        name = (options['name'] or long_id[:12]).lstrip('/')
        return options['host_namespace'] + '/' + name

    def get_container_log_file_list(self, long_id, options):
        assert isinstance(long_id, (str, unicode)), "long_id is not a string"
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
        assert isinstance(long_id, (str, unicode)), "long_id is not a string"
        return self.get_container_namespace(long_id, options)
