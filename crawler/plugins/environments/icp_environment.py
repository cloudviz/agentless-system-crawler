#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import logging
import copy
import re

from runtime_environment import IRuntimeEnvironment
from utils.dockerutils import exec_dockerinspect

logger = logging.getLogger('crawlutils')

META_CONFIG = 'Config'
META_LABELS = 'Labels'
META_UUID = 'Id'
META_HOSTNAME = 'Hostname'
META_REPOS = 'RepoTags'

K8S_NS_LABEL = "io.kubernetes.pod.namespace"
K8S_POD_LABEL = "io.kubernetes.pod.name"
K8S_CONTAINER_NAME_LABEL = "io.kubernetes.container.name"

CRAWLER_NAMESPACE_FORMAT = "{K8S_NS}/{K8S_POD}/{K8S_CONT_NAME}/{K8S_CONT_ID}"
CRAWLER_IMAGE_NAMESPACE_FORMAT = "{REPO_NS}/{IMAGE_NAME}:{IMAGE_TAG}"

# all of reg crawler target pod name is set to `regpod-checking`
regpod_pattern = re.compile("regpod-checking")

"""
ICP environment plugin is used by live crawler and registry crawler on ICP.
The role is to set adequate namespace depending on two source_types.
For container source type, it makes same namespace as kubernetes plugin.
For image source type, namespace is directly passed from --namespace arg.
That is because a launched container with the image may have many RepoTags,
so the plugin can not decide which repotag is suitable.
"""


class ICpEnvironment(IRuntimeEnvironment):
    name = 'icp'

    def get_environment_name(self):
        return self.name

    def get_container_namespace(self, long_id, options):
        assert isinstance(long_id, str) or unicode, "long_id is not a string"
        crawler_k8s_ns = ""
        container_meta = exec_dockerinspect(long_id)
        try:
            labels = container_meta.get(META_CONFIG).get(META_LABELS)
            if labels:
                podname = labels.get(K8S_POD_LABEL)
                if not podname:
                    logger.warning("%s is not icp managed container" % long_id)
                    return crawler_k8s_ns
                # (1). for reg crawler
                if regpod_pattern.search(podname):
                    crawler_k8s_ns = options.get("host_namespace")
                # (2). for live crawler
                else:
                    crawler_k8s_ns = CRAWLER_NAMESPACE_FORMAT.format(
                        K8S_NS=labels.get(K8S_NS_LABEL, ""),
                        K8S_POD=labels.get(K8S_POD_LABEL, ""),
                        K8S_CONT_NAME=labels.get(K8S_CONTAINER_NAME_LABEL, ""),
                        K8S_CONT_ID=long_id
                    )
        except KeyError:
            logger.error('Error retrieving container labels for: %s' %
                         long_id)
            pass

        return crawler_k8s_ns

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
