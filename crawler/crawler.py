#!/usr/bin/python
# -*- coding: utf-8 -*-

#
# Wrapper around the crawlutils module that provides:
# (a) an autonomous push mode via command-line invocation, and
# (b) a network pull mode via an HTTP REST interface (xxx CURRENTLY DISABLED)
#

import os
import sys
import logging
import logging.handlers
import time
import multiprocessing
import argparse
import json
from config_parser import (get_config,
                           apply_user_args,
                           parse_crawler_config)


# External dependencies that must be pip install'ed separately

import misc
import crawlutils
from crawlmodes import Modes

CRAWLER_HOST = misc.get_host_ipaddr()

logger = None


def csv_list(string):
    return string.split(',')


def setup_logger(logger_name, logfile='crawler.log', process_id=None):
    _logger = logging.getLogger(logger_name)
    _logger.setLevel(logging.INFO)
    (logfile_name, logfile_xtnsion) = os.path.splitext(logfile)
    if process_id is None:
        fname = logfile
    else:
        fname = '{0}-{1}{2}'.format(logfile_name, process_id,
                                    logfile_xtnsion)
    h = logging.handlers.RotatingFileHandler(filename=fname,
                                             maxBytes=10e6, backupCount=1)
    f = logging.Formatter(
        '%(asctime)s %(processName)-10s %(levelname)-8s %(message)s')
    h.setFormatter(f)
    _logger.addHandler(h)
    return _logger


def crawler_worker(process_id, logfile, params):
    logger = setup_logger('crawlutils', logfile, process_id)
    setup_logger('yapsy', logfile, process_id)

    # Starting message

    logger.info('*' * 50)
    logger.info('Crawler #%d started.' % (process_id))
    logger.info('*' * 50)

    crawlutils.snapshot(**params)


def start_autonomous_crawler(num_processes, logfile, params, options):

    setup_logger('crawler-main', logfile)
    logger = logging.getLogger('crawler-main')
    logger.info('Starting crawler at {0}'.format(CRAWLER_HOST))

    if params['crawlmode'] == 'OUTCONTAINER':
        jobs = []

        for index in xrange(num_processes):
            # XXX use options.get() instead
            options['partition_strategy'] = {'args': {}}
            options['partition_strategy']['name'] = 'equally_by_pid'
            partition_args = options['partition_strategy']['args']
            partition_args['process_id'] = index
            partition_args['num_processes'] = num_processes

            """
            XXX(ricarkol): remember that when we finally get rid of these
            worker processes in favor of a proper pool of working threads,
            we have to move the caches of previous metrics somewhere out of
            the FeaturesCrawler objects. And that cache has to be shared among
            all the working threads.
            """
            p = multiprocessing.Process(
                name='crawler-%s' %
                index, target=crawler_worker, args=(
                    index, logfile, params))
            jobs.append((p, index))
            p.start()
            logger.info('Crawler %s (pid=%s) started', index, p.pid)

        while jobs:
            for (index, (job, process_id)) in enumerate(jobs):
                if not job.is_alive():
                    exitcode = job.exitcode
                    pname = job.name
                    pid = job.pid
                    if job.exitcode:
                        logger.info(
                            '%s terminated unexpectedly with errorcode %s' %
                            (pname, exitcode))
                        for (other_job, process_id) in jobs:
                            if other_job != job:
                                logger.info(
                                    'Terminating crawler %s (pid=%s)',
                                    process_id,
                                    other_job.pid)
                                os.kill(other_job.pid, 9)
                        logger.info('Exiting as all jobs were terminated.'
                                    )
                        raise RuntimeError(
                            '%s terminated unexpectedly with errorcode %s' %
                            (pname, exitcode))
                    else:
                        logger.info(
                            'Crawler %s (pid=%s) exited normally.',
                            process_id,
                            pid)
                    del jobs[index]
            time.sleep(0.1)
        logger.info('Exiting as there are no more processes running.')
    else:

        # INVM, OUTVM, and others

        setup_logger('crawlutils', logfile, 0)
        crawlutils.snapshot(**params)


def main():

    euid = os.geteuid()
    if euid != 0:
        print 'Need to run this as root.'
        exit(1)

    parse_crawler_config()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--options',
        dest='options',
        type=str,
        default=None,
        help='JSON dict of crawler options (see README for defaults)')
    parser.add_argument(
        '--url',
        dest='url',
        type=str,
        nargs='+',
        default=None,
        help='Send the snapshot data to URL. Defaults to file://frame',
    )
    parser.add_argument(
        '--namespace',
        dest='namespace',
        type=str,
        nargs='?',
        default=None,
        help='Data source this crawler is associated with. Defaults to '
             '/localhost',
    )
    parser.add_argument(
        '--features',
        dest='features',
        type=csv_list,
        default=get_config()['general']['features_to_crawl'],
        help='Comma-separated list of feature-types to crawl. Defaults to '
             '{0}'.format(get_config()['general']['features_to_crawl']))
    parser.add_argument(
        '--since',
        dest='since',
        type=str,
        choices=[
            'EPOCH',
            'BOOT',
            'LASTSNAPSHOT'],
        default=None,
        help='Only crawl features touched since {EPOCH,BOOT,LASTSNAPSHOT}. '
             'Defaults to BOOT',
    )
    parser.add_argument(
        '--frequency',
        dest='frequency',
        type=int,
        default=None,
        help='Target time period for iterations. Defaults to -1 which '
             'means only run one iteration.')
    parser.add_argument(
        '--compress',
        dest='compress',
        type=str,
        choices=[
            'true',
            'false'],
        default='true' if get_config()['general']['compress'] else 'false',
        help='Whether to GZIP-compress the output frame data, must be one of '
             '{true,false}. Defaults to true',
    )
    parser.add_argument('--logfile', dest='logfile', type=str,
                        default='crawler.log',
                        help='Logfile path. Defaults to crawler.log')
    parser.add_argument(
        '--crawlmode',
        dest='crawlmode',
        type=str,
        choices=[
            Modes.INVM,
            Modes.OUTVM,
            Modes.MOUNTPOINT,
            Modes.OUTCONTAINER,
            Modes.MESOS,
        ],
        default=Modes.INVM,
        help='The crawler mode: '
             '{INVM,OUTVM,MOUNTPOINT,OUTCONTAINER}. '
             'Defaults to INVM',
    )
    parser.add_argument(
        '--mountpoint',
        dest='mountpoint',
        type=str,
        default=get_config()['general']['default_mountpoint'],
        help='Mountpoint location (required for --crawlmode MOUNTPOINT)')
    parser.add_argument(
        '--inputfile',
        dest='inputfile',
        type=str,
        default=None,
        help='Path to file that contains frame data (required for '
             '--crawlmode FILE)')
    parser.add_argument(
        '--format',
        dest='format',
        type=str,
        default='csv',
        choices=['csv', 'graphite', 'json'],
        help='Emitted data format.',
    )
    parser.add_argument(
        '--crawlContainers',
        dest='crawlContainers',
        type=str,
        nargs='?',
        default='ALL',
        help='List of containers to crawl as a list of Docker container IDs. '
             'If this is not passed, then just the host is crawled. '
             'Alternatively the word "ALL" can be used to crawl every '
             'container. "ALL" will crawl all namespaces including the host '
             'itself. This option is only valid for INVM crawl mode. Example: '
             '--crawlContainers 5f3380d2319e,681be3e32661',
    )
    parser.add_argument(
        '--crawlVMs',
        dest='crawl_vm',
        nargs='+',
        default=None,
        help='List of VMs to crawl'
             'Default is \'ALL\' VMs'
             'Currently need following as input for each VM'
             '\'vm_name, kernel_version_long, linux_flavour, arch\''
             'Auto kernel version detection in future, when only vm names'
             '(\'ALL\' by default) would need to be passed'
             'Example --crawlVM'
             'vm1,3.13.0-24-generic_3.13.0-24.x86_64,ubuntu,x86_64'
             'vm2,4.0.3.x86_64,vanilla,x86_64',
    )
    parser.add_argument(
        '--environment',
        dest='environment',
        type=str,
        default=get_config()['general']['environment'],
        help='This speficies some environment specific behavior, like how '
             'to name a container. The way to add a new behavior is by '
             'implementing a plugin (see plugins/cloudsight_environment.py '
             'as an example. Defaults to "cloudsight".',
    )
    parser.add_argument(
        '--pluginmode',
        dest='pluginmode',
        action='store_true',
        default=get_config()['general']['plugin_mode'],
        help='If --pluginmode is given, then only enabled plugins in'
             'config/*.conf are loaded,'
             'else legacy mode is run via CLI'
    )
    parser.add_argument(
        '--plugins',
        dest='plugin_places',
        type=csv_list,
        default=get_config()['general']['plugin_places'],
        help='This is a comma separated list of directories where to find '
             'plugins. Each path can be an absolute, or a relative to the '
             'location of the crawler.py.',
    )
    parser.add_argument(
        '--numprocesses',
        dest='numprocesses',
        type=int,
        default=None,
        help='Number of processes used for container crawling. Defaults '
             'to the number of cores.')
    parser.add_argument(
        '--extraMetadataFile',
        dest='extraMetadataFile',
        type=str,
        default=None,
        help='Json file with data to be annotate all features. It can be used '
             'to append a set of system identifiers to the metadata feature '
             'and if the --extraMetadataForAll')

    parser.add_argument(
        '--extraMetadataForAll',
        dest='extraMetadataForAll',
        action='store_true',
        default=False,
        help='If specified all features are appended with extra metadata.')
    parser.add_argument(
        '--linkContainerLogFiles',
        dest='linkContainerLogFiles',
        action='store_true',
        default=get_config()['general']['link_container_log_files'],
        help='Experimental feature. If specified and if running in '
             'OUTCONTAINER mode, then the crawler maintains links to '
             'container log files.')
    parser.add_argument(
        '--overwrite',
        dest='overwrite',
        action='store_true',
        default=False,
        help='overwrite file type url parameter and strip trailing '
             'sequence number')
    parser.add_argument(
        '--avoidSetns',
        dest='avoid_setns',
        action='store_true',
        default=False,
        help='Avoids the use of the setns() syscall to crawl containers. '
             'Some features like process will not work with this option. '
             'Only applies to the OUTCONTAINER mode'
    )

    args = parser.parse_args()
    params = {}

    params['options'] = {}
    if args.options:
        try:
            _options = json.loads(args.options)
        except (KeyError, ValueError):
            sys.stderr.write('Can not parse the user options json.\n')
            sys.exit(1)
        for (option, value) in _options.iteritems():
            params['options'][option] = value

    options = params['options']

    if args.url:
        params['urls'] = args.url
    if args.namespace:
        params['namespace'] = args.namespace
    if args.features:
        params['features'] = args.features
    if args.since:
        params['since'] = args.since
    if args.frequency is not None:
        params['frequency'] = args.frequency
    options['compress'] = (args.compress in ['true', 'True'])
    params['overwrite'] = args.overwrite
    if args.crawlmode:
        params['crawlmode'] = args.crawlmode

        if args.crawlmode == 'MOUNTPOINT':
            if not args.mountpoint:
                print ('Need to specify mountpoint location (--mountpoint) '
                       'for MOUNTPOINT mode')
                sys.exit(1)
            if os.path.exists(args.mountpoint):
		options['root_dir'] = args.mountpoint
		options['os'] = {}
		options['os']['root_dir'] = args.mountpoint
		options['package'] = {}
		options['package']['root_dir'] = args.mountpoint
		options['file'] = {}
		options['file']['root_dir'] = args.mountpoint
		# To remove args.mountpoint (e.g. /mnt/CrawlDisk) from each
		# reported file path.
		options['file']['root_dir_alias'] = '/'
		options['config'] = {}
		options['config']['root_dir'] = args.mountpoint
		# To remove args.mountpoint (e.g. /mnt/CrawlDisk) from each
		# reported file path.
		options['config']['root_dir_alias'] = '/'

        if args.crawlmode == 'OUTCONTAINER':
            if args.crawlContainers:
                options['docker_containers_list'] = args.crawlContainers
            if not args.numprocesses:
                args.numprocesses = multiprocessing.cpu_count()
            #if args.avoid_setns:
            #    options['os']['avoid_setns'] = args.avoid_setns
            #    options['config']['avoid_setns'] = args.avoid_setns
            #    options['file']['avoid_setns'] = args.avoid_setns
            #    options['package']['avoid_setns'] = args.avoid_setns

        options['avoid_setns'] = args.avoid_setns

        if args.crawlmode == 'OUTVM':
            if args.crawl_vm:
                options['vm_list'] = args.crawl_vm

    if args.format:
        params['format'] = args.format
    if args.environment:
        options['environment'] = args.environment
    options['pluginmode'] = args.pluginmode
    if args.plugin_places:
        options['plugin_places'] = args.plugin_places
    if args.extraMetadataFile:
        options['metadata'] = {}
        metadata = options['metadata']
        metadata['extra_metadata_for_all'] = args.extraMetadataForAll
        try:
            with open(args.extraMetadataFile, 'r') as fp:
                metadata['extra_metadata'] = fp.read()
        except Exception as e:
            print 'Could not read the feature metadata json file: %s' \
                % e
            sys.exit(1)
    options['link_container_log_files'] = args.linkContainerLogFiles

    apply_user_args(options=options)

    start_autonomous_crawler(args.numprocesses, args.logfile, params, options)


if __name__ == '__main__':
    main()
