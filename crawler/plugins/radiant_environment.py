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

try:
    import crawler.dockerutils
except ImportError:
    import dockerutils

CONTAINER_META_CONFIG = 'Config'
CONTAINER_META_LABELS = 'Labels'
CONTAINER_META_TENANT = 'com.swarm.tenant.0'
CONTAINER_META_UUID = 'Id'
NAMESPACE_TAG_SEPERATOR = '.'
CONTAINER_META_HOSTNAME = "Hostname"

logger = logging.getLogger('crawlutils')

class RadiantEnvironment(IRuntimeEnvironment):
    name = 'radiant'

    def get_environment_name(self):
        return self.name

    def get_container_namespace(self, long_id, options):
	assert type(long_id) is str or unicode, "long_id is not a string"
        namespace = None
        container_meta = dockerutils.exec_dockerinspect(long_id)
        uuid = container_meta[CONTAINER_META_UUID]
        try:
            tenantId = container_meta[CONTAINER_META_CONFIG][CONTAINER_META_LABELS][CONTAINER_META_TENANT]
        except KeyError:
            tenantId = container_meta[CONTAINER_META_CONFIG][CONTAINER_META_HOSTNAME]
 
        namespace = "{TENANT}{SEPERATOR}{UUID}".format(
                    TENANT = tenantId,
                    SEPERATOR = NAMESPACE_TAG_SEPERATOR,
                    UUID = uuid)

        logging.debug("namespace created: %s"%(namespace))

        return namespace		

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
