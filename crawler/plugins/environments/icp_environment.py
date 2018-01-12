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
META_REPO = 'RepoTag'

K8S_NS_LABEL = "io.kubernetes.pod.namespace"
K8S_POD_LABEL = "io.kubernetes.pod.name"
K8S_CONTAINER_NAME_LABEL = "io.kubernetes.container.name"

CRAWLER_CONT_NAMESPACE_FORMAT = "icp/{K8S_NS}/{K8S_POD}/{K8S_CONT_ID}"
CRAWLER_IMAGE_NAMESPACE_FORMAT = "icp/{IMAGE_NAME}"

regpod_pattern = re.compile("regpod-checking")


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
                # for reg crawler
                if regpod_pattern.search(podname):
                    # repotag format == "repository/k8s-ns/imagename:tag"
                    repotag = container_meta.get(META_REPO)
                    peaces = repotag.split("/")
                    ns_image_tag = peaces[1] + "/" + peaces[2]
                    crawler_k8s_ns = CRAWLER_IMAGE_NAMESPACE_FORMAT.format(
                        IMAGE_NAME=ns_image_tag
                    )
                # for live crawler
                else:
                    crawler_k8s_ns = CRAWLER_CONT_NAMESPACE_FORMAT.format(
                        K8S_NS=labels.get(K8S_NS_LABEL, ""),
                        K8S_POD=labels.get(K8S_POD_LABEL, ""),
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
