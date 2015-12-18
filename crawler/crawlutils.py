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
import cPickle as pickle


# External dependencies that must be pip install'ed separately

import simplejson as json
import psutil

from emitter import Emitter
from features_crawler import FeaturesCrawler
from containers import (get_filtered_list_of_containers,
                        do_link_container_log_files,
                        new_urls_for_container,
                        get_ctr_namespace)
import defaults
import misc
from crawlmodes import Modes
from namespace import signal_handler

logger = logging.getLogger('crawlutils')


def snapshot_single_frame(
    emitter,
    featurelist,
    options,
    crawler=None,
    inputfile="undefined",
):

    # Special-casing Reading from a frame file as input here:
    # - Sweep through entire file, if feature.type is in featurelist, emit
    #   feature.key and feature.value
    # - Emit also validates schema as usual, so do not try to pass
    #   noncompliant stuff in the input frame file; it will bounce.

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

                # print 'feature.type:', feature_data.type, '\nfeature.key:',
                # feature_data.key, '\nfeature.value:', feature_data.value

                num_features += 1

                # Emit only if in the specified features-to-crawl list

                if feature_data.type in featurelist:
                    emitter.emit(feature_data.key, feature_data.value,
                                 feature_data.type)
            logger.info('Read %d feature rows from %s' % (num_features,
                                                          inputfile))
    else:
        for ftype in featurelist:
            fopts = options.get(ftype,
                                defaults.DEFAULT_CRAWL_OPTIONS.get(ftype,
                                                                   None))
            if fopts is None:
                continue
            if ftype == 'os':
                if crawlmode in [Modes.INVM, Modes.OUTCONTAINER]:
                    for (key, feature) in crawler.crawl_os(**fopts):
                        emitter.emit(key, feature)
            if ftype == 'disk':
                if crawlmode in [Modes.INVM, Modes.OUTCONTAINER]:
                    for (key, feature) in \
                            crawler.crawl_disk_partitions(**fopts):
                        emitter.emit(key, feature)
                else:
                    logger.warning('Cannot crawl feature: ' + ftype +
                                   ' in crawl mode: ' + crawlmode +
                                   '. Skipping...')
            if ftype == 'metric':
                if crawlmode in [Modes.INVM, Modes.OUTCONTAINER]:
                    for (key, feature) in \
                            crawler.crawl_metrics(**fopts):
                        emitter.emit(key, feature)
                else:
                    logger.warning('Cannot crawl feature: ' + ftype +
                                   ' in crawl mode: ' + crawlmode +
                                   '. Skipping...')
            if ftype == 'process':
                if crawlmode in [Modes.INVM, Modes.OUTVM, Modes.OUTCONTAINER]:
                    for (key, feature) in \
                            crawler.crawl_processes(**fopts):
                        emitter.emit(key, feature)
                else:
                    logger.warning('Cannot crawl feature: ' + ftype +
                                   ' in crawl mode: ' + crawlmode +
                                   '. Skipping...')
            if ftype == 'connection':
                if crawlmode in [Modes.INVM, Modes.OUTVM, Modes.OUTCONTAINER]:
                    for (key, feature) in \
                            crawler.crawl_connections(**fopts):
                        emitter.emit(key, feature)
                else:
                    logger.warning('Cannot crawl feature: ' + ftype +
                                   ' in crawl mode: ' + crawlmode +
                                   '. Skipping...')
            if ftype == 'package':
                if crawlmode in [Modes.INVM, Modes.OUTCONTAINER]:
                    for (key, feature) in \
                            crawler.crawl_packages(**fopts):
                        emitter.emit(key, feature)
            if ftype == 'file':
                if crawlmode in [Modes.INVM, Modes.OUTCONTAINER]:
                    for (key, feature) in crawler.crawl_files(**fopts):
                        emitter.emit(key, feature)
            if ftype == 'config':
                for (key, feature) in \
                        crawler.crawl_config_files(**fopts):
                    emitter.emit(key, feature)
            if ftype == 'memory':
                if crawlmode in [Modes.INVM, Modes.OUTVM, Modes.OUTCONTAINER]:
                    for (key, feature) in crawler.crawl_memory(**fopts):
                        emitter.emit(key, feature)
                else:
                    logger.warning('Cannot crawl feature: ' + ftype +
                                   ' in crawl mode: ' + crawlmode +
                                   '. Skipping...')
            if ftype == 'cpu':
                if crawlmode in [Modes.INVM, Modes.OUTVM]:
                    fopts['per_cpu'] = True
                    for (key, feature) in crawler.crawl_cpu(**fopts):
                        emitter.emit(key, feature)
                if crawlmode in [Modes.OUTCONTAINER]:
                    fopts['per_cpu'] = False
                    for (key, feature) in crawler.crawl_cpu(**fopts):
                        emitter.emit(key, feature)
                else:
                    logger.warning('Cannot crawl feature: ' + ftype +
                                   ' in crawl mode: ' + crawlmode +
                                   '. Skipping...')
            if ftype == 'interface':
                if crawlmode in [Modes.INVM, Modes.OUTCONTAINER]:
                    for (key, feature) in \
                            crawler.crawl_interface(**fopts):
                        emitter.emit(key, feature)
                else:
                    logger.warning('Cannot crawl feature: ' + ftype +
                                   ' in crawl mode: ' + crawlmode +
                                   '. Skipping...')
            if ftype == 'load':
                if crawlmode in [Modes.INVM, Modes.OUTCONTAINER]:
                    for (key, feature) in crawler.crawl_load(**fopts):
                        emitter.emit(key, feature)
                else:
                    logger.warning('Cannot crawl feature: ' + ftype +
                                   ' in crawl mode: ' + crawlmode +
                                   '. Skipping...')
            if ftype == 'dockerps':
                if crawlmode in [Modes.INVM]:
                    for (key, feature) in \
                            crawler.crawl_dockerps(**fopts):
                        emitter.emit(key, feature, 'dockerps')
                else:
                    logger.warning('Cannot crawl feature: ' + ftype +
                                   ' in crawl mode: ' + crawlmode +
                                   '. Skipping...')
            if ftype == 'dockerhistory':
                if crawlmode in [Modes.OUTCONTAINER]:
                    for (key, feature) in \
                            crawler.crawl_dockerhistory(**fopts):
                        emitter.emit(key, feature, 'dockerhistory')
                else:
                    logger.warning('Cannot crawl feature: ' + ftype +
                                   ' in crawl mode: ' + crawlmode +
                                   '. Skipping...')
            if ftype == 'dockerinspect':
                if crawlmode in [Modes.OUTCONTAINER]:
                    for (key, feature) in \
                            crawler.crawl_dockerinspect(**fopts):
                        emitter.emit(key, feature, 'dockerinspect')
                else:
                    logger.warning('Cannot crawl feature: ' + ftype +
                                   ' in crawl mode: ' + crawlmode +
                                   '. Skipping...')


def snapshot_generic(
    metadata,
    crawlmode,
    urls,
    snapshot_num,
    featurelist,
    options,
    format,
    inputfile,
):

    crawler = FeaturesCrawler(feature_epoch=metadata['since_timestamp'
                                                     ], crawl_mode=crawlmode)
    output_urls = [('{0}.{1}'.format(u, snapshot_num)
                    if u.startswith('file:') else u) for u in urls]

    crawler.namespace = metadata['namespace']
    metadata['system_type'] = 'vm'

    with Emitter(
        urls=output_urls,
        emitter_args=metadata,
        format=format,
    ) as emitter:
        snapshot_single_frame(emitter, featurelist,
                              options, crawler, inputfile)
        emitter.close_file()


def snapshot_all_containers(
    metadata,
    urls,
    snapshot_num,
    featurelist,
    options,
    format,
    inputfile,
):

    host_namespace = metadata['namespace']
    environment = options['environment']
    link_container_log_files = options['link_container_log_files']
    user_list = options['docker_containers_list']
    partition_strategy = options['partition_strategy']
    container_long_id_to_namespace_map = options[
        'metadata']['container_long_id_to_namespace_map']

    filtered_list = get_filtered_list_of_containers(
        user_list,
        partition_strategy
    )

    logger.debug('Crawling %d containers' % (len(filtered_list)))

    # For all containers that were not filtered out

    for container in filtered_list:

        # Setup the namespace of the container
        namespace = get_ctr_namespace(
            host_namespace,
            container,
            environment,
            container_long_id_to_namespace_map)
        container.namespace = namespace

    # Link the container log files into a known location in the host

    if link_container_log_files:
        do_link_container_log_files(filtered_list, environment, options)

    # For all containers that were not filtered out

    for container in filtered_list:

        # The fact that a namespace exist or not for that container is what we
        # use to decide whether we should crawl that container or not.

        if not namespace:
            continue

        logger.info('Crawling container %s %s %s' %
                    (container.pid, container.short_id, container.namespace))
        crawler = FeaturesCrawler(
            feature_epoch=metadata['since_timestamp'],
            crawl_mode=Modes.OUTCONTAINER,
            namespace=container.namespace,
            container=container)

        metadata['namespace'] = container.namespace
        metadata['system_type'] = 'container'
        metadata['container_long_id'] = container.long_id
        metadata['container_name'] = container.name
        metadata['container_image'] = container.image
        output_urls = new_urls_for_container(
            urls, container.short_id, container.pid, snapshot_num)

        with Emitter(
            urls=output_urls,
            emitter_args=metadata,
            format=format,
        ) as emitter:

            # This check is racy. If the container dies while we crawl it, an
            # exception will be raised and we will continue to the next
            # container. This check is a slight performance improvement: fail
            # early and move on quickly.

            if container.isRunning():
                snapshot_single_frame(emitter, featurelist, options,
                                      crawler, inputfile)


def snapshot(
    urls=['stdout://'],
    namespace=misc.get_host_ipaddr(),
    features=defaults.DEFAULT_FEATURES_TO_CRAWL,
    options=defaults.DEFAULT_CRAWL_OPTIONS,
    since='BOOT',
    frequency=-1,
    crawlmode=Modes.INVM,
    inputfile='Undefined',
    format='csv',
    parent_pid=None,
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
    :param frequency: Sleep duration between iterations. -1 means just one run.
    :param crawlmode: What's the system we want to crawl.
    :param inputfile: Applies to mode.FILE. The frame emitted is this file.
    :param format: The format of the frame, defaults to csv.
    :param parent_pid: XXX hacky, used to check if parent is alive.
    """

    saved_args = locals()
    logger.debug('snapshot args: %s' % (saved_args))

    if crawlmode == Modes.MOUNTPOINT:
        mountpoint = options['mountpoint']
        logger.debug('Snapshot: mountpoint={0}'.format(mountpoint))
    if crawlmode == Modes.FILE:
        logger.debug('Snapshot: input frame file={0}'.format(inputfile))
    if crawlmode not in [Modes.INVM, Modes.OUTCONTAINER] and since != 'EPOCH':
        since = 'EPOCH'
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
            since = 'BOOT'
            # subsequent snapshots will update this value
            since_timestamp = last_snapshot_time

    if 'file' in options and 'root_dir' in options['file']:
        misc.log_atime_config(path=options['file']['root_dir'],
                              crawlmode=crawlmode)
    else:
        misc.log_atime_config('/', crawlmode=crawlmode)

    featurelist = features.split(',')
    snapshot_num = 0

    # When running in OUTCONTAINER mode, some features_crawler.crawl_* start
    # worker processes. Let's be sure we kill them when we die.
    if parent_pid and crawlmode == 'OUTCONTAINER':
        signal.signal(signal.SIGTERM, signal_handler)

    compress = options['compress']
    extra_metadata = options['metadata']['extra_metadata']
    extra_metadata_for_all = options['metadata']['extra_metadata_for_all']

    while True:
        logger.debug('snapshot #{0}'.format(snapshot_num))

        snapshot_time = int(time.time())
        metadata = {
            'namespace': namespace,
            'features': features,
            'timestamp': snapshot_time,
            'since': since,
            'since_timestamp': since_timestamp,
            'compress': compress,
            'extra': extra_metadata,
            'extra_all_features': extra_metadata_for_all,
        }

        if crawlmode == Modes.OUTCONTAINER:

            # Containers (not limited to docker containers)

            snapshot_all_containers(
                metadata=metadata,
                urls=urls,
                snapshot_num=snapshot_num,
                featurelist=featurelist,
                options=options,
                format=format,
                inputfile=inputfile,
            )
        else:

            # Anything besides containers, typically from inside a VM

            snapshot_generic(
                metadata=metadata,
                crawlmode=crawlmode,
                urls=urls,
                snapshot_num=snapshot_num,
                featurelist=featurelist,
                options=options,
                format=format,
                inputfile=inputfile,
            )

        # Check the parent

        if not misc.is_process_running(parent_pid):
            logger.info('Main process with pid %d died, so exiting.'
                        % parent_pid)
            raise Exception('Main process %d died.' % parent_pid)

        # Exit the process.

        if frequency <= 0:
            break

        if since == 'LASTSNAPSHOT':
            # Subsequent snapshots will update this value.
            since_timestamp = snapshot_time
        time.sleep(frequency)
        snapshot_num += 1
