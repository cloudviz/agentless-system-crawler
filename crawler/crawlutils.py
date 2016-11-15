#!/usr/bin/python
# -*- coding: utf-8 -*-

#
# Collection of crawlers that extract specific types of features from
# the host machine. This code is portable across OS platforms (Linux, Windows)
#


import logging
import time
import signal
from ctypes import CDLL
import uuid
import psutil
from mesos import snapshot_crawler_mesos_frame

try:
    libc = CDLL('libc.so.6')
except Exception as e:
    libc = None


# External dependencies that must be pip install'ed separately

from emitter import Emitter
from containers import get_filtered_list_of_containers
import misc
from crawlmodes import Modes
import plugins_manager

logger = logging.getLogger('crawlutils')


"""
This flag is checked at each iteration of the main crawling loop, and while
crawling all features for a specific system (container or local system).
"""
should_exit = False


def signal_handler_exit(signum, stack):
    global should_exit
    logger.info('Got signal to exit ..')
    should_exit = True


def snapshot_generic(
    crawlmode=Modes.INVM,
    urls=['stdout://'],
    snapshot_num=0,
    features=['os'],
    compress=False,
    options={},
    format='csv',
    namespace='',
    ignore_exceptions=True
):

    metadata = {
        'namespace': namespace,
        'features': ','.join(map(str, features)),
        'timestamp': int(time.time()),
        'system_type': 'vm',
        'compress': compress,
    }

    output_urls = [('{0}.{1}'.format(u, snapshot_num)
                    if u.startswith('file:') else u) for u in urls]

    host_crawl_plugins = plugins_manager.get_host_crawl_plugins(features)

    with Emitter(
        urls=output_urls,
        emitter_args=metadata,
        format=format,
    ) as emitter:
        for (plugin_obj, plugin_args) in host_crawl_plugins:
            try:
                if should_exit:
                    break
                for (key, val, feature_type) in plugin_obj.crawl(
                        **plugin_args):
                    emitter.emit(key, val, feature_type)
            except Exception as exc:
                logger.exception(exc)
                if not ignore_exceptions:
                    raise exc


def snapshot_mesos(
    crawlmode=Modes.MESOS,
    urls=['stdout://'],
    snapshot_num=0,
    features=[],
    compress=False,
    options={},
    format='csv',
    namespace='',
    ignore_exceptions=True,
):
    metadata = {
        'namespace': namespace,
        'timestamp': int(time.time()),
        'system_type': 'mesos',
        'compress': compress,
    }

    output_urls = [('{0}.{1}'.format(u, snapshot_num)
                    if u.startswith('file:') else u) for u in urls]

    with Emitter(
        urls=output_urls,
        emitter_args=metadata,
        format=format,
    ) as emitter:
        frame = snapshot_crawler_mesos_frame()
        emitter.emit('mesos', frame)


def sanitize_vm_list(vm_list):

    _vm_list = []
    for vm_desc in vm_list:
        vm_name, vm_kernel, vm_distro, vm_arch = vm_desc.split(',')

        for proc in psutil.process_iter():
            if 'qemu' in proc.name():
                line = proc.cmdline()
                if vm_name == line[line.index('-name') + 1]:
                    vm = (
                        vm_name, str(proc.pid), vm_kernel, vm_distro, vm_arch)
                    _vm_list.append(vm)
                    found_qemu_pid = True

        if found_qemu_pid is False:
            raise ValueError('no VM with vm_name: %s' % vm_name)

    return _vm_list


def reformat_output_urls(urls, name, snapshot_num):
    """
    Reformat output URLs to include the snapshot_num and the system name
    """
    output_urls = []
    for url in urls:
        if url.startswith('file:'):
            file_suffix = ''
            file_suffix = '{0}.{1}'.format(name, snapshot_num)
            output_urls.append('{0}.{1}'.format(url, file_suffix))
        else:
            output_urls.append(url)
    return output_urls


def snapshot_vms(
    urls=['stdout://'],
    snapshot_num=0,
    features=['os'],
    compress=False,
    options={},
    format='csv',
    namespace='',
    ignore_exceptions=True
):

    # Default will become ALL from None, when auto kernel detection
    # gets merged
    vm_list = options.get('vm_list', None)

    if vm_list is None:
        raise ValueError('need list of VMs (with descriptors) to crawl!')
        # When None gets changed to ALL, this will not be raised

    # convert VM descriptor for each VM to
    # (vm_name, qemu_pid, kernel_version_long, distro, arch)
    # from input type: 'vm_name, kernel_version_long, distro, arch'
    vm_list = sanitize_vm_list(vm_list)

    for vm in vm_list:
        vm_name = vm[0]
        vm = vm[1:]

        metadata = {
            'namespace': namespace,
            'features': ','.join(map(str, features)),
            'timestamp': int(time.time()),
            'system_type': 'vm',
            'compress': compress,
        }

        output_urls = reformat_output_urls(urls, vm_name, snapshot_num)

        vm_crawl_plugins = plugins_manager.get_vm_crawl_plugins(features)

        with Emitter(
            urls=output_urls,
            emitter_args=metadata,
            format=format,
        ) as emitter:
            for (plugin_obj, plugin_args) in vm_crawl_plugins:
                try:
                    if should_exit:
                        break
                    for (key, val, feature_type) in plugin_obj.crawl(
                            vm_desc=vm, **plugin_args):
                        emitter.emit(key, val, feature_type)
                except Exception as exc:
                    logger.exception(exc)
                    if not ignore_exceptions:
                        raise exc


def snapshot_container(
    urls=['stdout://'],
    snapshot_num=0,
    features=['os'],
    compress=False,
    options={},
    format='csv',
    container=None,
    ignore_exceptions=True
):
    global should_exit

    if not container:
        raise ValueError('snapshot_container can only be called with a '
                         'container object already initialized.')

    metadata = options.get('metadata', {})
    extra_metadata = metadata.get('extra_metadata', {})
    extra_metadata_for_all = metadata.get('extra_metadata_for_all', False)

    metadata = {
        'namespace': container.namespace,
        'system_type': 'container',
        'features': ','.join(map(str, features)),
        'timestamp': int(time.time()),
        'compress': compress,
        'container_long_id': container.long_id,
        'container_name': container.name,
        'container_image': container.image,
        'extra': extra_metadata,
        'extra_all_features': extra_metadata_for_all,
        'uuid': str(uuid.uuid4())
    }

    if container.is_docker_container():
        metadata['owner_namespace'] = container.owner_namespace
        metadata['docker_image_long_name'] = container.docker_image_long_name
        metadata['docker_image_short_name'] = container.docker_image_short_name
        metadata['docker_image_tag'] = container.docker_image_tag
        metadata['docker_image_registry'] = container.docker_image_registry

    output_urls = reformat_output_urls(urls, container.short_id, snapshot_num)

    container_crawl_plugins = plugins_manager.get_container_crawl_plugins(
        features=features)

    with Emitter(
        urls=output_urls,
        emitter_args=metadata,
        format=format,
    ) as emitter:
        for (plugin_obj, plugin_args) in container_crawl_plugins:
            try:
                if should_exit:
                    break
                for (key, val, typ) in plugin_obj.crawl(
                        container_id=container.long_id, **plugin_args):
                    emitter.emit(key, val, typ)
            except Exception as exc:
                logger.exception(exc)
                if not ignore_exceptions:
                    raise exc


def snapshot_containers(
    containers,
    urls=['stdout://'],
    snapshot_num=0,
    features=['os'],
    compress=False,
    environment='cloudsight',
    options={},
    format='csv',
    ignore_exceptions=True,
    host_namespace='',
    link_log_files=False
):

    user_list = options.get('docker_containers_list', 'ALL')
    partition_strategy = options.get('partition_strategy', {})

    curr_containers = get_filtered_list_of_containers(
        environment=environment,
        user_list=user_list,
        partition_strategy=partition_strategy,
        host_namespace=host_namespace)
    deleted = [c for c in containers if c not in curr_containers]
    containers = curr_containers

    for container in deleted:
        if link_log_files:
            try:
                container.unlink_logfiles()
            except NotImplementedError:
                pass

    logger.debug('Crawling %d containers' % (len(containers)))

    for container in containers:

        logger.info(
            'Crawling container %s %s %s' %
            (container.pid, container.short_id, container.namespace))

        if link_log_files:
            # This is a NOP if files are already linked (which is
            # pretty much always).
            try:
                container.link_logfiles()
            except NotImplementedError:
                pass

        # no feature crawling
        if 'nofeatures' in features:
            continue
        snapshot_container(
            urls=urls,
            snapshot_num=snapshot_num,
            features=features,
            compress=compress,
            options=options,
            format=format,
            container=container,
        )
    return containers


def _get_next_iteration_time(next_iteration_time, frequency, snapshot_time):
    if frequency == 0:
        return (0, 0)

    if next_iteration_time is None:
        next_iteration_time = snapshot_time + frequency
    else:
        next_iteration_time = next_iteration_time + frequency

    while next_iteration_time + frequency < time.time():
        next_iteration_time = next_iteration_time + frequency

    time_to_sleep = next_iteration_time - time.time()
    return (time_to_sleep, next_iteration_time)


def load_plugins(
    features=['os', 'cpu'],
    options={}
):
    plugins_manager.reload_env_plugin(options=options)

    plugins_manager.reload_container_crawl_plugins(
        features=features,
        options=options)

    plugins_manager.reload_vm_crawl_plugins(
        features=features,
        options=options)

    plugins_manager.reload_host_crawl_plugins(
        features=features,
        options=options)


def snapshot(
    urls=['stdout://'],
    namespace=misc.get_host_ipaddr(),
    features=['os', 'cpu'],
    options={},
    frequency=-1,
    crawlmode=Modes.INVM,
    format='csv',
    first_snapshot_num=0,
    max_snapshots=-1
):
    """Entrypoint for crawler functionality.

    This is the function executed by long running crawler processes. It just
    loops sleeping for `frequency` seconds at each crawl interval.  During each
    interval, it collects the features listed in `features`, and sends them to
    the outputs listed in `urls`.

    :param urls: The url used as the output of the snapshot.
    :param namespace: This a pointer to a specific system (e.g. IP for INVM).
    :param features: List of features to crawl.
    :param options: Tree of options with details like what config files.
    :param frequency: Target time period for iterations. -1 means just one run.
    :param crawlmode: What's the system we want to crawl.
    :param format: The format of the frame, defaults to csv.
    """

    global should_exit
    saved_args = locals()
    logger.debug('snapshot args: %s' % (saved_args))

    compress = False
    environment = options.get('environment', 'cloudsight')

    load_plugins(features, options)

    next_iteration_time = None

    snapshot_num = first_snapshot_num

    # Die if the parent dies
    PR_SET_PDEATHSIG = 1
    try:
        libc.prctl(PR_SET_PDEATHSIG, signal.SIGHUP)
        signal.signal(signal.SIGHUP, signal_handler_exit)
    except AttributeError:
        logger.warning('prctl is not available. MacOS is not supported.')

    containers = []

    # This is the main loop of the system, taking a snapshot and sleeping at
    # every iteration.

    while True:

        snapshot_time = int(time.time())

        if crawlmode == Modes.OUTCONTAINER:
            containers = snapshot_containers(
                containers=containers,
                urls=urls,
                snapshot_num=snapshot_num,
                features=features,
                compress=compress,
                environment=environment,
                options=options,
                format=format,
                host_namespace=namespace,
                link_log_files=options.get('link_container_log_files', False)
            )
        elif crawlmode == Modes.MESOS:
            snapshot_mesos(
                crawlmode=crawlmode,
                urls=urls,
                snapshot_num=snapshot_num,
                compress=compress,
                options=options,
                format=format,
                namespace=namespace,
            )
        elif crawlmode == Modes.OUTVM:
            snapshot_vms(
                urls=urls,
                snapshot_num=snapshot_num,
                features=features,
                compress=compress,
                options=options,
                format=format,
                namespace=namespace
            )
        elif crawlmode in [Modes.INVM, Modes.MOUNTPOINT]:
            snapshot_generic(
                crawlmode=crawlmode,
                urls=urls,
                snapshot_num=snapshot_num,
                features=features,
                compress=compress,
                options=options,
                format=format,
                namespace=namespace
            )
        else:
            raise NotImplementedError('Crawl mode %s is not implemented' %
                                      crawlmode)

        # Frequency < 0 means only one run.
        if (frequency < 0 or should_exit or snapshot_num == max_snapshots):
            logger.info('Bye')
            break

        time_to_sleep, next_iteration_time = _get_next_iteration_time(
            next_iteration_time, frequency, snapshot_time)
        if time_to_sleep > 0:
            time.sleep(time_to_sleep)

        snapshot_num += 1
