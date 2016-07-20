#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Collection of crawlers that extract specific types of features from
# the host machine. This code is portable across OS platforms (Linux, Windows)
#


import sys
import os
import logging
from collections import namedtuple, OrderedDict
import time
import csv
import signal
import json
from ctypes import CDLL
import uuid
from crawler_mesos import snapshot_crawler_mesos_frame

try:
    libc = CDLL('libc.so.6')
except Exception as e:
    libc = None

# External dependencies that must be pip install'ed separately

import psutil
from yapsy.PluginManager import PluginManager

from emitter import Emitter
from features_crawler import FeaturesCrawler
from containers import get_filtered_list_of_containers
import defaults
import misc
from crawlmodes import Modes
from runtime_environment import IRuntimeEnvironment
from crawler_exceptions import RuntimeEnvironmentPluginNotFound

logger = logging.getLogger('crawlutils')


"""This flag is check at each iteration of the main crawling loop, and while
crawling all features for a specific system (container or local system).
"""
should_exit = False


def signal_handler_exit(signum, stack):
    global should_exit
    logger.info('Got signal to exit ..')
    should_exit = True


def load_env_plugin(plugin_places=[misc.execution_path('plugins')],
                    environment='cloudsight'):
    pm = PluginManager(plugin_info_ext='plugin')

    # Normalize the paths to the location of this file.
    # XXX-ricarkol: there has to be a better way to do this.
    plugin_places = [misc.execution_path(x) for x in plugin_places]

    pm.setPluginPlaces(plugin_places)
    pm.setCategoriesFilter({"RuntimeEnvironment": IRuntimeEnvironment})
    pm.collectPlugins()

    for env_plugin in pm.getAllPlugins():
        # There should be only one plugin of the given category and type;
        # but in case there are more, pick the first one.
        if env_plugin.plugin_object.get_environment_name() == environment:
            return env_plugin.plugin_object
    raise RuntimeEnvironmentPluginNotFound('Could not find a valid runtime '
                                           'environment plugin at %s' % plugin_places)


def snapshot_single_frame(
    emitter,
    features=defaults.DEFAULT_FEATURES_TO_CRAWL,
    options=defaults.DEFAULT_CRAWL_OPTIONS,
    crawler=None,
    inputfile="undefined",
    ignore_exceptions=True,
):

    # Special-casing Reading from a frame file as input here:
    # - Sweep through entire file, if feature.type is in features, emit
    #   feature.key and feature.value
    # - Emit also validates schema as usual, so do not try to pass
    #   noncompliant stuff in the input frame file; it will bounce.

    global should_exit
    crawlmode = crawler.crawl_mode
    if crawlmode == Modes.FILE:
        logger.debug(
            'Reading features from local frame file {0}'.format(inputfile))
        FeatureFormat = namedtuple('FeatureFormat', ['type', 'key',
                                                     'value'])
        if inputfile is None or not os.path.exists(inputfile):
            logger.error('Input frame file: ' + inputfile +
                         ' does not exist.')
        with open(inputfile, 'r') as fd:
            csv.field_size_limit(sys.maxsize)  # to handle large values
            csv_reader = csv.reader(fd, delimiter='\t', quotechar="'")
            num_features = 0
            for row in csv_reader:
                feature_data = FeatureFormat(
                    row[0], json.loads(
                        row[1]), json.loads(
                        row[2], object_pairs_hook=OrderedDict))

                num_features += 1

                # Emit only if in the specified features-to-crawl list

                if feature_data.type in features:
                    emitter.emit(feature_data.key, feature_data.value,
                                 feature_data.type)
            logger.info('Read %d feature rows from %s' % (num_features,
                                                          inputfile))
    else:
        for feature in features.split(','):
            feature_options = options.get(
                feature, defaults.DEFAULT_CRAWL_OPTIONS[feature])
            if should_exit:
                break
            if feature_options is None:
                continue
            try:
                _crawl_single_feature(feature,
                                      feature_options,
                                      crawlmode,
                                      crawler,
                                      emitter)
            except Exception as e:
                logger.exception(e)
                if not ignore_exceptions:
                    raise e


def _crawl_single_feature(feature,
                          feature_options,
                          crawlmode,
                          crawler,
                          emitter):
    if feature == 'os':
        if crawlmode in [Modes.INVM, Modes.OUTCONTAINER, Modes.MOUNTPOINT]:
            for (key, feature) in crawler.crawl_os(**feature_options):
                emitter.emit(key, feature)
    if feature == 'disk':
        if crawlmode in [Modes.INVM, Modes.OUTCONTAINER, Modes.MOUNTPOINT]:
            for (key, feature) in \
                    crawler.crawl_disk_partitions(**feature_options):
                emitter.emit(key, feature)
        else:
            logger.warning('Cannot crawl feature: ' + feature +
                           ' in crawl mode: ' + crawlmode +
                           '. Skipping...')
    if feature == 'metric':
        if crawlmode in [Modes.INVM, Modes.OUTCONTAINER]:
            for (key, feature) in \
                    crawler.crawl_metrics(**feature_options):
                emitter.emit(key, feature)
        else:
            logger.warning('Cannot crawl feature: ' + feature +
                           ' in crawl mode: ' + crawlmode +
                           '. Skipping...')
    if feature == 'process':
        if crawlmode in [Modes.INVM, Modes.OUTVM, Modes.OUTCONTAINER]:
            for (key, feature) in \
                    crawler.crawl_processes(**feature_options):
                emitter.emit(key, feature)
        else:
            logger.warning('Cannot crawl feature: ' + feature +
                           ' in crawl mode: ' + crawlmode +
                           '. Skipping...')
    if feature == 'connection':
        if crawlmode in [Modes.INVM, Modes.OUTVM, Modes.OUTCONTAINER]:
            for (key, feature) in \
                    crawler.crawl_connections(**feature_options):
                emitter.emit(key, feature)
        else:
            logger.warning('Cannot crawl feature: ' + feature +
                           ' in crawl mode: ' + crawlmode +
                           '. Skipping...')
    if feature == 'package':
        if crawlmode in [Modes.INVM, Modes.OUTCONTAINER, Modes.MOUNTPOINT]:
            for (key, feature) in \
                    crawler.crawl_packages(**feature_options):
                emitter.emit(key, feature)
    if feature == 'file':
        if crawlmode in [Modes.INVM, Modes.OUTCONTAINER, Modes.MOUNTPOINT]:
            for (key, feature) in crawler.crawl_files(**feature_options):
                emitter.emit(key, feature)
    if feature == 'config':
        for (key, feature) in \
                crawler.crawl_config_files(**feature_options):
            emitter.emit(key, feature)
    if feature == 'memory':
        if crawlmode in [Modes.INVM, Modes.OUTVM, Modes.OUTCONTAINER]:
            for (key, feature) in crawler.crawl_memory(**feature_options):
                emitter.emit(key, feature)
        else:
            logger.warning('Cannot crawl feature: ' + feature +
                           ' in crawl mode: ' + crawlmode +
                           '. Skipping...')
    if feature == 'cpu':
        if crawlmode in [Modes.INVM, Modes.OUTVM]:
            feature_options['per_cpu'] = True
            for (key, feature) in crawler.crawl_cpu(**feature_options):
                emitter.emit(key, feature)
        elif crawlmode in [Modes.OUTCONTAINER]:
            feature_options['per_cpu'] = False
            for (key, feature) in crawler.crawl_cpu(**feature_options):
                emitter.emit(key, feature)
        else:
            logger.warning('Cannot crawl feature: ' + feature +
                           ' in crawl mode: ' + crawlmode +
                           '. Skipping...')
    if feature == 'interface':
        if crawlmode in [Modes.INVM, Modes.OUTCONTAINER]:
            for (key, feature) in \
                    crawler.crawl_interface(**feature_options):
                emitter.emit(key, feature)
        else:
            logger.warning('Cannot crawl feature: ' + feature +
                           ' in crawl mode: ' + crawlmode +
                           '. Skipping...')
    if feature == 'load':
        if crawlmode in [Modes.INVM, Modes.OUTCONTAINER]:
            for (key, feature) in crawler.crawl_load(**feature_options):
                emitter.emit(key, feature)
        else:
            logger.warning('Cannot crawl feature: ' + feature +
                           ' in crawl mode: ' + crawlmode +
                           '. Skipping...')
    if feature == 'dockerps':
        if crawlmode in [Modes.INVM]:
            for (key, feature) in \
                    crawler.crawl_dockerps(**feature_options):
                emitter.emit(key, feature, 'dockerps')
        else:
            logger.warning('Cannot crawl feature: ' + feature +
                           ' in crawl mode: ' + crawlmode +
                           '. Skipping...')
    if feature == 'dockerhistory':
        if crawlmode in [Modes.OUTCONTAINER]:
            for (key, feature) in \
                    crawler.crawl_dockerhistory(**feature_options):
                emitter.emit(key, feature, 'dockerhistory')
        else:
            logger.warning('Cannot crawl feature: ' + feature +
                           ' in crawl mode: ' + crawlmode +
                           '. Skipping...')
    if feature == 'dockerinspect':
        if crawlmode in [Modes.OUTCONTAINER]:
            for (key, feature) in \
                    crawler.crawl_dockerinspect(**feature_options):
                emitter.emit(key, feature, 'dockerinspect')
        else:
            logger.warning('Cannot crawl feature: ' + feature +
                           ' in crawl mode: ' + crawlmode +
                           '. Skipping...')
    if feature == '_test_infinite_loop':
        for (key, feature) in \
                crawler.crawl_test_infinite_loop(**feature_options):
            emitter.emit(key, feature)
    if feature == '_test_crash':
        for (key, feature) in \
                crawler.crawl_test_crash(**feature_options):
            emitter.emit(key, feature)


def snapshot_generic(
    crawlmode=Modes.INVM,
    urls=['stdout://'],
    snapshot_num=0,
    features=defaults.DEFAULT_FEATURES_TO_CRAWL,
    options=defaults.DEFAULT_CRAWL_OPTIONS,
    format='csv',
    inputfile='undefined',
    overwrite=False,
    namespace='',
    since='BOOT',
    since_timestamp=0,
):

    crawler = FeaturesCrawler(feature_epoch=since_timestamp,
                              crawl_mode=crawlmode,
                              namespace=namespace)

    compress = options['compress']
    metadata = {
        'namespace': namespace,
        'features': features,
        'timestamp': int(time.time()),
        'system_type': 'vm',
        'since': since,
        'since_timestamp': since_timestamp,
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
        snapshot_single_frame(emitter, features,
                              options, crawler, inputfile)

def snapshot_mesos(
    crawlmode=Modes.MESOS,
    inurl=['stdin://'],
    urls=['stdout://'],
    snapshot_num=0,
    options=defaults.DEFAULT_CRAWL_OPTIONS,
    format='csv',
    inputfile='undefined',
    overwrite=False,
    namespace='',
    since='BOOT',
    since_timestamp=0,
):

    mesos_stats = snapshot_crawler_mesos_frame(inurl)
    
    compress = options['compress']
    metadata = {
        'namespace': namespace,
        'timestamp': int(time.time()),
        'system_type': 'mesos',
        'since': since,
        'since_timestamp': since_timestamp,
        'compress': compress,
        'overwrite': overwrite,
    }
    for mesos_key, mesos_value in mesos_stats.iteritems():
        print mesos_key

    output_urls = [('{0}.{1}'.format(u, snapshot_num)
                    if u.startswith('file:') else u) for u in urls]

    with Emitter(
        urls=output_urls,
        emitter_args=metadata,
        format=format,
    ) as emitter:
       snapshot_crawler_mesos_frame(inurl)


def snapshot_container(
    urls=['stdout://'],
    snapshot_num=0,
    features=defaults.DEFAULT_FEATURES_TO_CRAWL,
    options=defaults.DEFAULT_CRAWL_OPTIONS,
    format='csv',
    inputfile='undefined',
    overwrite=False,
    container=None,
    since='BOOT',
    since_timestamp=0,
):
    crawler = FeaturesCrawler(
        feature_epoch=since_timestamp,
        crawl_mode=Modes.OUTCONTAINER,
        namespace=container.namespace,
        container=container)

    compress = options['compress']
    extra_metadata = options['metadata']['extra_metadata']
    extra_metadata_for_all = options['metadata']['extra_metadata_for_all']

    metadata = {
        'namespace': container.namespace,
        'system_type': 'container',
        'features': features,
        'timestamp': int(time.time()),
        'since': since,
        'since_timestamp': since_timestamp,
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

        snapshot_single_frame(emitter, features, options,
                              crawler, inputfile)


def get_initial_since_values(since):
    last_snapshot_time = (
        psutil.boot_time() if hasattr(
            psutil, 'boot_time') else psutil.BOOT_TIME)
    if since == 'EPOCH':
        since_timestamp = 0
    elif since == 'BOOT':
        since_timestamp = (
            psutil.boot_time() if hasattr(
                psutil, 'boot_time') else psutil.BOOT_TIME)

    elif since == 'LASTSNAPSHOT':
        # subsequent snapshots will update this value
        since_timestamp = last_snapshot_time
    else:

        # check if the value of since is a UTC timestamp (integer)

        try:
            since_timestamp = int(since)
        except:
            logger.error(
                'Invalid value since={0}, defaulting to BOOT'.format(since))
            # subsequent snapshots will update this value
            since_timestamp = last_snapshot_time
    return since_timestamp, last_snapshot_time


def snapshot(
    inurl=['stdin://'],
    urls=['stdout://'],
    namespace=misc.get_host_ipaddr(),
    features=defaults.DEFAULT_FEATURES_TO_CRAWL,
    options=defaults.DEFAULT_CRAWL_OPTIONS,
    since='BOOT',
    frequency=-1,
    crawlmode=Modes.INVM,
    inputfile='Undefined',
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
    :param since: Calculate deltas or not. XXX needs some work.
    :param frequency: Target time period for iterations. -1 means just one run.
    :param crawlmode: What's the system we want to crawl.
    :param inputfile: Applies to mode.FILE. The frame emitted is this file.
    :param format: The format of the frame, defaults to csv.
    """

    global should_exit
    saved_args = locals()
    logger.debug('snapshot args: %s' % (saved_args))

    assert('metadata' in options)
    environment = options.get('environment', defaults.DEFAULT_ENVIRONMENT)
    plugin_places = options.get('plugin_places',
                                defaults.DEFAULT_PLUGIN_PLACES).split(',')
    runtime_env = load_env_plugin(plugin_places=plugin_places,
                                  environment=environment)

    since_timestamp, last_snapshot_time = get_initial_since_values(since)
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

            curr_containers = get_filtered_list_of_containers(
                options, namespace)
            deleted = [c for c in containers if c not in curr_containers]
            containers = curr_containers

            for container in deleted:
                if options.get('link_container_log_files', False):
                    container.unlink_logfiles(options)

            logger.debug('Crawling %d containers' % (len(containers)))

            for container in containers:

                logger.info(
                    'Crawling container %s %s %s' %
                    (container.pid, container.short_id, container.namespace))

                if options.get('link_container_log_files', False):
                    # This is a NOP if files are already linked (which is
                    # pretty much always).
                    container.link_logfiles(options=options)

                # no feature crawling
                if 'nofeatures' in features:
                    continue
                snapshot_container(
                    urls=urls,
                    snapshot_num=snapshot_num,
                    features=features,
                    options=options,
                    format=format,
                    inputfile=inputfile,
                    container=container,
                    since=since,
                    since_timestamp=since_timestamp,
                    overwrite=overwrite
                )

        elif crawlmode in (Modes.INVM,
                           Modes.MOUNTPOINT,
                           Modes.DEVICE,
                           Modes.FILE,
                           Modes.ISCSI):

            snapshot_generic(
                crawlmode=crawlmode,
                urls=urls,
                snapshot_num=snapshot_num,
                features=features,
                options=options,
                format=format,
                inputfile=inputfile,
                namespace=namespace,
                since=since,
                since_timestamp=since_timestamp,
                overwrite=overwrite
            )
        elif crawlmode in (Modes.MESOS):
            snapshot_mesos(
                crawlmode=crawlmode,
                inurl=inurl,
                urls=urls,
                snapshot_num=snapshot_num,
                options=options,
                format=format,
                inputfile=inputfile,
                overwrite=overwrite,
                namespace=namespace,
                since=since,
                since_timestamp=since_timestamp
            )
        else:
            raise RuntimeError('Unknown Mode')

        if since == 'LASTSNAPSHOT':
            # Subsequent snapshots will update this value.
            since_timestamp = snapshot_time

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
