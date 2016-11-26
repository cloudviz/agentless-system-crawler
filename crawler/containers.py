#!/usr/bin/python
# -*- coding: utf-8 -*-
import logging

# External dependencies that must be pip install'ed separately

import container
import misc
from dockercontainer import list_docker_containers

logger = logging.getLogger('crawlutils')


def list_all_containers(user_list='ALL', host_namespace='',
                        ignore_raw_containers=True):
    """
    Returns a list of all running containers in the host.

    :param user_list: list of Docker container IDs. TODO: include rkt Ids.
    :param host_namespace: string representing the host name (e.g. host IP)
    :param ignore_raw_containers: if True, only include Docker or rkt.
    An example of a non-docker container is a chromium-browser process.
    :return: a list of Container objects
    """
    visited_ns = set()  # visited PID namespaces

    for _container in list_docker_containers(host_namespace, user_list):
        curr_ns = _container.process_namespace
        if curr_ns not in visited_ns:
            visited_ns.add(curr_ns)
            yield _container

    # XXX get list of rkt containers

    if ignore_raw_containers:
        return

    for _container in container.list_raw_containers(user_list):
        curr_ns = _container.process_namespace
        if curr_ns not in visited_ns:
            visited_ns.add(curr_ns)
            yield _container


def get_containers(
    environment='cloudsight',
    host_namespace=misc.get_host_ipaddr(),
    user_list='ALL',
    ignore_raw_containers=True
):
    """
    Returns a list of all containers running in the host.

    XXX This list excludes non-docker containers when running in non-cloudsight
    environment. TODO: fix this weird behaviour.

    :param environment: this defines how the name (namespace) is constructed.
    :param host_namespace: string representing the host name (e.g. host IP)
    :param user_list: list of Docker container IDs. TODO: include rkt.
    :param ignore_raw_containers: if True, only include Docker or rkt.
    An example of a non-docker container is a chromium-browser process.
    :return: a list of Container objects.
    """
    filtered_list = []
    containers_list = list_all_containers(user_list, host_namespace,
                                          ignore_raw_containers)
    for _container in containers_list:
        default_environment = 'cloudsight'
        if (environment != default_environment and
                not _container.is_docker_container()):
            continue

        filtered_list.append(_container)

    return filtered_list
