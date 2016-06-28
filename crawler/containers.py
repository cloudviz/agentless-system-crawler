#!/usr/bin/python
# -*- coding: utf-8 -*-
import logging

# External dependencies that must be pip install'ed separately

import psutil

import defaults
from container import Container
import misc
import namespace
from dockercontainer import list_docker_containers
from crawler_exceptions import ContainerInvalidEnvironment

logger = logging.getLogger('crawlutils')


def list_all_containers(user_list='ALL',
                        container_opts={},
                        ):
    """
    Returns a list of all running containers, as `Container` objects.

    A running container is defined as a process subtree with the `pid`
    namespace different to the `init` process `pid` namespace.
    """
    all_docker_containers = list_docker_containers(container_opts)

    if user_list in ['ALL', 'all', 'All']:
        init_ns = namespace.get_pid_namespace(1)

        visited_ns = set()  # visited PID namespaces

        # Start with all docker containers

        for container in all_docker_containers:
            curr_ns = namespace.get_pid_namespace(container.pid)
            if not curr_ns:
                continue
            if curr_ns not in visited_ns and curr_ns != init_ns:
                visited_ns.add(curr_ns)
                try:
                    yield container
                except ContainerInvalidEnvironment as e:
                    logger.exception(e)

        # Continue with all other containers not known to docker

        for p in psutil.process_iter():
            pid = (p.pid() if hasattr(p.pid, '__call__') else p.pid)
            if pid == 1 or pid == '1':

                # don't confuse the init process as a container

                continue
            if misc.process_is_crawler(p):

                # don't confuse the crawler process with a container

                continue
            curr_ns = namespace.get_pid_namespace(pid)
            if not curr_ns:

                # invalid container

                continue
            if curr_ns not in visited_ns and curr_ns != init_ns:
                visited_ns.add(curr_ns)
                yield Container(pid)
    else:

        # User provided a list of containers

        user_containers = user_list.split(',')
        for container in all_docker_containers:
            short_id_match = container.short_id in user_containers
            long_id_match = container.long_id in user_containers
            if short_id_match or long_id_match:
                yield container


def get_filtered_list_of_containers(
    options=defaults.DEFAULT_CRAWL_OPTIONS,
    host_namespace=misc.get_host_ipaddr(),
):
    """
    Returns a partition of all the Container objects currently running in the
    system and set the `namespace` and metadata of these containers.

    The partitioning is given by `partition_strategy`.
    """
    environment = options.get('environment', defaults.DEFAULT_ENVIRONMENT)
    metadata = options.get('metadata', {})
    _map = metadata.get('container_long_id_to_namespace_map', {})
    container_opts = {'host_namespace': host_namespace,
                      'environment': environment,
                      'long_id_to_namespace_map': _map,
                      'container_logs': options['logcrawler']['default_log_files']
                      }

    user_list = options.get('docker_containers_list', 'ALL')
    partition_strategy = options.get('partition_strategy', None)

    assert(partition_strategy['name'] == 'equally_by_pid')
    process_id = partition_strategy['args']['process_id']
    num_processes = partition_strategy['args']['num_processes']

    filtered_list = []
    containers_list = list_all_containers(user_list, container_opts)
    for container in containers_list:

        # The partition strategy is to split all the containers equally by
        # process pid. We do it by hashing the long_id of the container.

        _hash = container.long_id
        num = int(_hash, 16) % int(num_processes)
        if num == process_id:

            try:
                container.setup_namespace_and_metadata(container_opts)
            except ContainerInvalidEnvironment:
                continue

            if not container.namespace:
                continue

            filtered_list.append(container)

    return filtered_list