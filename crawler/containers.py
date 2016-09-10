#!/usr/bin/python
# -*- coding: utf-8 -*-
import logging

# External dependencies that must be pip install'ed separately

import defaults
import container
import misc
from dockercontainer import list_docker_containers

logger = logging.getLogger('crawlutils')


def list_all_containers(user_list='ALL',
                        container_opts={},
                        ):
    """
    Returns a list of all running containers, as `Container` objects.

    A running container is defined as a process subtree with the `pid`
    namespace different to the `init` process `pid` namespace.
    """
    visited_ns = set()  # visited PID namespaces

    for _container in list_docker_containers(container_opts, user_list):
        curr_ns = _container.process_namespace
        if curr_ns not in visited_ns:
            visited_ns.add(curr_ns)
            yield _container

    for _container in container.list_raw_containers(user_list):
        curr_ns = _container.process_namespace
        if curr_ns not in visited_ns:
            visited_ns.add(curr_ns)
            yield _container


def get_filtered_list_of_containers(
    options=defaults.DEFAULT_CRAWL_OPTIONS,
    host_namespace=misc.get_host_ipaddr()
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
                      }

    user_list = options.get('docker_containers_list', 'ALL')
    partition_strategy = options.get('partition_strategy', None)

    assert(partition_strategy['name'] == 'equally_by_pid')
    process_id = partition_strategy['args']['process_id']
    num_processes = partition_strategy['args']['num_processes']

    filtered_list = []
    containers_list = list_all_containers(user_list, container_opts)
    for _container in containers_list:

        """
        There are docker and non-docker containers in this list. An example of
        a non-docker container is a chromium-browser process.
        TODO(kollerr): the logic that defines whether a container is acceptable
        to a plugin or not should be in the plugin itself.
        """

        if (environment != defaults.DEFAULT_ENVIRONMENT and
                not _container.is_docker_container()):
            continue

        """
        The partition strategy is to split all the containers equally by
        process pid. We do it by hashing the long_id of the container.
        """

        _hash = _container.long_id
        num = int(_hash, 16) % int(num_processes)
        if num == process_id:
            filtered_list.append(_container)

    return filtered_list
