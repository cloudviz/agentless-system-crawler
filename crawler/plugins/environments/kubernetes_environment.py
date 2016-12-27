#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import logging
import copy

from runtime_environment import IRuntimeEnvironment
from utils.dockerutils import exec_dockerinspect

logger = logging.getLogger('crawlutils')

META_CONFIG = 'Config'
META_LABELS = 'Labels'
META_UUID = 'Id'
META_HOSTNAME = 'Hostname'


class KubernetesEnvironment(IRuntimeEnvironment):
    name = 'kubernetes'

    def get_environment_name(self):
        return self.name

    def get_container_namespace(self, long_id, options):
        assert isinstance(long_id, str) or unicode, "long_id is not a string"
        k8s_meta = dict()
        container_meta = exec_dockerinspect(long_id)
        try:
            labels = container_meta.get(META_CONFIG).get(META_LABELS)
            k8s_meta[META_UUID] = container_meta.get(META_UUID, None)
            if labels:
                k8s_meta.update(labels)

        except KeyError:
            logger.error('Error retrieving container labels for: %s' %
                         long_id)
            pass

        return k8s_meta

    def get_container_log_file_list(self, long_id, options):
        assert isinstance(long_id, str) or unicode, "long_id is not a string"
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
        assert isinstance(long_id, str) or unicode, "long_id is not a string"
        assert 'name' in options and 'host_namespace' in options
        name = options['name']
        name = (name if len(name) > 0 else long_id[:12])
        name = (name[1:] if name[0] == '/' else name)
        return options['host_namespace'] + '/' + name
