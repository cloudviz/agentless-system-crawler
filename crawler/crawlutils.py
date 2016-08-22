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
from mesos import snapshot_crawler_mesos_frame

try:
    libc = CDLL('libc.so.6')
except Exception as e:
    libc = None

# External dependencies that must be pip install'ed separately

from emitter import Emitter
import features_crawler
from containers import get_filtered_list_of_containers
import defaults
import misc
from crawlmodes import Modes
import plugins_manager

logger = logging.getLogger('crawlutils')


"""This flag is check at each iteration of the main crawling loop, and while
crawling all features for a specific system (container or local system).
"""
should_exit = False


def signal_handler_exit(signum, stack):
    global should_exit
    logger.info('Got signal to exit ..')
    should_exit = True


def _snapshot_single_frame(
    emitter,
    features=defaults.DEFAULT_FEATURES_TO_CRAWL,
    options=defaults.DEFAULT_CRAWL_OPTIONS,
    crawler=None,
    ignore_exceptions=True,
):

    global should_exit

    for feature in features.split(','):
        feature_options = options.get(
            feature, defaults.DEFAULT_CRAWL_OPTIONS[feature])
        if should_exit:
            break
        if feature_options is None:
            continue
        try:
            for (key, val) in crawler.funcdict[feature](**feature_options):
                emitter.emit(key, val, feature)
        except Exception as exc:
            logger.exception(exc)
            if not ignore_exceptions:
                raise exc


def snapshot_generic(
    crawlmode=Modes.INVM,
    urls=['stdout://'],
    snapshot_num=0,
    features=defaults.DEFAULT_FEATURES_TO_CRAWL,
    options=defaults.DEFAULT_CRAWL_OPTIONS,
    format='csv',
    overwrite=False,
    namespace='',
    ignore_exceptions=True
):

    crawler = features_crawler.FeaturesCrawler(crawl_mode=crawlmode)

    metadata = {
        'namespace': namespace,
        'features': features,
        'timestamp': int(time.time()),
        'system_type': 'vm',
        'compress': options['compress'],
        'overwrite': overwrite,
    }

    output_urls = [('{0}.{1}'.format(u, snapshot_num)
                    if u.startswith('file:') else u) for u in urls]

    with Emitter(
        urls=output_urls,
        emitter_args=metadata,
        format=format,
    ) as emitter:
        _snapshot_single_frame(emitter=emitter,
                               features=features,
                               options=options,
                               crawler=crawler,
                               ignore_exceptions=ignore_exceptions)


def snapshot_mesos(
    crawlmode=Modes.MESOS,
    urls=['stdout://'],
    snapshot_num=0,
    features=None,
    options=defaults.DEFAULT_CRAWL_OPTIONS,
    format='csv',
    overwrite=False,
    namespace='',
    ignore_exceptions=True,
):
    compress = options['compress']
    metadata = {
        'namespace': namespace,
        'timestamp': int(time.time()),
        'system_type': 'mesos',
        'compress': compress,
        'overwrite': overwrite,
    }

    output_urls = [('{0}.{1}'.format(u, snapshot_num)
                    if u.startswith('file:') else u) for u in urls]

    with Emitter(
        urls=output_urls,
        emitter_args=metadata,
        format=format,
    ) as emitter:
        frame = snapshot_crawler_mesos_frame(options['mesos_url'])
        emitter.emit('mesos', frame)


def snapshot_container(
    urls=['stdout://'],
    snapshot_num=0,
    features=defaults.DEFAULT_FEATURES_TO_CRAWL,
    options=defaults.DEFAULT_CRAWL_OPTIONS,
    format='csv',
    overwrite=False,
    container=None,
    ignore_exceptions=True,
):
    if not container:
        raise ValueError('snapshot_container can only be called with a '
                         'container object already initialized.')

    crawler = features_crawler.FeaturesCrawler(crawl_mode=Modes.OUTCONTAINER,
                                               container=container)

    compress = options['compress']
    extra_metadata = options['metadata']['extra_metadata']
    extra_metadata_for_all = options['metadata']['extra_metadata_for_all']

    metadata = {
        'namespace': container.namespace,
        'system_type': 'container',
        'features': features,
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

    output_urls = []
    for url in urls:
        if url.startswith('file:'):
            file_suffix = ''
            if overwrite is True:
                file_suffix = '{0}'.format(container.name)
            else:
                file_suffix = '{0}.{1}'.format(
                    container.short_id, snapshot_num)
            output_urls.append('{0}.{1}'.format(url, file_suffix))
        else:
            output_urls.append(url)

    with Emitter(
        urls=output_urls,
        emitter_args=metadata,
        format=format,
    ) as emitter:

        _snapshot_single_frame(emitter=emitter,
                               features=features,
                               options=options,
                               crawler=crawler,
                               ignore_exceptions=ignore_exceptions)


def snapshot(
    urls=['stdout://'],
    namespace=misc.get_host_ipaddr(),
    features=defaults.DEFAULT_FEATURES_TO_CRAWL,
    options=defaults.DEFAULT_CRAWL_OPTIONS,
    frequency=-1,
    crawlmode=Modes.INVM,
    format='csv',
    overwrite=False,
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

    assert('metadata' in options)
    environment = options.get('environment', defaults.DEFAULT_ENVIRONMENT)
    plugin_places = options.get('plugin_places',
                                defaults.DEFAULT_PLUGIN_PLACES).split(',')
    plugins_manager.reload_env_plugin(plugin_places=plugin_places,
                                      environment=environment)

    next_iteration_time = None

    snapshot_num = 0

    # Die if the parent dies
    PR_SET_PDEATHSIG = 1
    libc.prctl(PR_SET_PDEATHSIG, signal.SIGHUP)
    signal.signal(signal.SIGHUP, signal_handler_exit)

    if crawlmode == Modes.OUTCONTAINER:
        containers = get_filtered_list_of_containers(options, namespace)

    # This is the main loop of the system, taking a snapshot and sleeping at
    # every iteration.

    while True:

        snapshot_time = int(time.time())

        if crawlmode == Modes.OUTCONTAINER:

            curr_containers = get_filtered_list_of_containers(options,
                                                              namespace)
            deleted = [c for c in containers if c not in curr_containers]
            containers = curr_containers

            for container in deleted:
                if options.get('link_container_log_files', False):
                    try:
                        container.unlink_logfiles(options)
                    except NotImplementedError:
                        pass

            logger.debug('Crawling %d containers' % (len(containers)))

            for container in containers:

                logger.info(
                    'Crawling container %s %s %s' %
                    (container.pid, container.short_id, container.namespace))

                if options.get('link_container_log_files', False):
                    # This is a NOP if files are already linked (which is
                    # pretty much always).
                    try:
                        container.link_logfiles(options=options)
                    except NotImplementedError:
                        pass

                # no feature crawling
                if 'nofeatures' in features:
                    continue
                snapshot_container(
                    urls=urls,
                    snapshot_num=snapshot_num,
                    features=features,
                    options=options,
                    format=format,
                    container=container,
                    overwrite=overwrite
                )

        elif crawlmode in (Modes.INVM,
                           Modes.MOUNTPOINT):

            snapshot_generic(
                crawlmode=crawlmode,
                urls=urls,
                snapshot_num=snapshot_num,
                features=features,
                options=options,
                format=format,
                namespace=namespace,
                overwrite=overwrite
            )
        elif crawlmode in (Modes.MESOS):
            snapshot_mesos(
                crawlmode=crawlmode,
                urls=urls,
                snapshot_num=snapshot_num,
                options=options,
                format=format,
                overwrite=overwrite,
                namespace=namespace,
            )
        else:
            raise RuntimeError('Unknown Mode')

        # Frequency <= 0 means only one run.
        if frequency < 0 or should_exit:
            logger.info('Bye')
            break
        elif frequency == 0:
            continue

        if next_iteration_time is None:
            next_iteration_time = snapshot_time + frequency
        else:
            next_iteration_time = next_iteration_time + frequency

        while next_iteration_time + frequency < time.time():
            next_iteration_time = next_iteration_time + frequency

        time_to_sleep = next_iteration_time - time.time()
        if time_to_sleep > 0:
            time.sleep(time_to_sleep)

        snapshot_num += 1
