#!/usr/bin/python
# -*- coding: utf-8 -*-

import argparse
import json
import os

from worker import Worker
from containers_crawler import ContainersCrawler
from utils import misc
from crawlmodes import Modes
from emitters_manager import EmittersManager
from host_crawler import HostCrawler
from vms_crawler import VirtualMachinesCrawler

logger = None


def csv_list(string):
    return string.split(',')


def json_parser(string):
    return json.loads(string)


def main():

    euid = os.geteuid()
    if euid != 0:
        print 'Need to run this as root.'
        exit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--options',
        dest='options',
        type=json_parser,
        default={},
        help='JSON dict of crawler options used to be passed as arguments'
             'to the crawler plugins.'
    )
    parser.add_argument(
        '--url',
        dest='url',
        type=csv_list,
        default=['stdout://'],
        help='Send the snapshot data to URL. Defaults to the console.',
    )
    parser.add_argument(
        '--namespace',
        dest='namespace',
        type=str,
        nargs='?',
        default=misc.get_host_ipaddr(),
        help='Data source this crawler is associated with. Defaults to '
             '/localhost',
    )
    parser.add_argument(
        '--features',
        dest='features',
        type=csv_list,
        default=['os', 'cpu'],
        help='Comma-separated list of feature-types to crawl. Defaults to '
             'os,cpu',
    )
    parser.add_argument(
        '--frequency',
        dest='frequency',
        type=int,
        default=-1,
        help='Target time period for iterations. Defaults to -1 which '
             'means only run one iteration.'
    )
    parser.add_argument(
        '--compress',
        dest='compress',
        action='store_true',
        default=False,
        help='Whether to GZIP-compress the output frame data, must be one of '
             '{true,false}. Defaults to false',
    )
    parser.add_argument('--logfile', dest='logfile', type=str,
                        default='crawler.log',
                        help='Logfile path. Defaults to crawler.log'
                        )
    parser.add_argument(
        '--crawlmode',
        dest='crawlmode',
        type=str,
        choices=[
            Modes.INVM,
            Modes.OUTVM,
            Modes.MOUNTPOINT,
            Modes.OUTCONTAINER,
            Modes.OUTCONTAINERSAFE,
            Modes.MESOS,
        ],
        default=Modes.INVM,
        help='The crawler mode: '
             '{INVM,OUTVM,MOUNTPOINT,OUTCONTAINER,OUTCONTAINERSAFE}. '
             'Defaults to INVM',
    )
    parser.add_argument(
        '--mountpoint',
        dest='mountpoint',
        type=str,
        default='/',
        help='Mountpoint location used as the / for features like packages,'
             'files, config'
    )
    parser.add_argument(
        '--format',
        dest='format',
        type=str,
        default='csv',
        choices=['csv', 'graphite', 'json', 'logstash'],
        help='Emitted data format.',
    )
    parser.add_argument(
        '--crawlContainers',
        dest='crawlContainers',
        type=str,
        nargs='?',
        default='ALL',
        help='List of containers to crawl as a list of Docker container IDs'
             '(only Docker is supported at the moment). ' 'Defaults to all '
             'running containers. Example: --crawlContainers aaa,bbb',
    )
    parser.add_argument(
        '--crawlVMs',
        dest='vm_descs_list',
        nargs='+',
        default='ALL',
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
        default='cloudsight',
        help='This speficies some environment specific behavior, like how '
             'to name a container. The way to add a new behavior is by '
             'implementing a plugin (see plugins/cloudsight_environment.py '
             'as an example. Defaults to "cloudsight".',
    )
    parser.add_argument(
        '--plugins',
        dest='plugin_places',
        type=csv_list,
        default=['plugins'],
        help='This is a comma separated list of directories where to find '
             'plugins. Each path can be an absolute, or a relative to the '
             'location of the crawler.py. Default is "plugins"',
    )
    parser.add_argument(
        '--numprocesses',
        dest='numprocesses',
        type=int,
        default=1,
        help='Number of processes used for container crawling. Defaults '
             'to the number of cores. NOT SUPPORTED.'
    )
    parser.add_argument(
        '--extraMetadata',
        dest='extraMetadata',
        type=json_parser,
        default={},
        help='Json with data to annotate all features. It can be used '
             'to append a set of system identifiers to the metadata feature '
             'and if the --extraMetadataForAll'
    )
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
    misc.setup_logger('crawlutils', args.logfile)
    misc.setup_logger('yapsy', 'yapsy.log')

    options = args.options
    options['avoid_setns'] = args.avoid_setns
    options['mountpoint'] = args.mountpoint

    emitters = EmittersManager(urls=args.url,
                               format=args.format,
                               compress=args.compress,
                               extra_metadata=args.extraMetadata,
                               plugin_places=args.plugin_places)

    if args.crawlmode == 'OUTCONTAINER':
        crawler = ContainersCrawler(
            features=args.features,
            environment=args.environment,
            user_list=args.crawlContainers,
            host_namespace=args.namespace,
            plugin_places=args.plugin_places,
            options=options)
    elif args.crawlmode == 'INVM' or args.crawlmode == 'MOUNTPOINT':
        crawler = HostCrawler(
            features=args.features,
            namespace=args.namespace,
            plugin_places=args.plugin_places,
            options=options)
    elif args.crawlmode == 'OUTVM':
        crawler = VirtualMachinesCrawler(
            features=args.features,
            user_list=args.vm_descs_list,
            host_namespace=args.namespace,
            plugin_places=args.plugin_places,
            options=options)
    elif args.crawlmode == 'OUTCONTAINERSAFE':
        crawler = SafeContainersCrawler(
            features=args.features,
            environment=args.environment,
            user_list=args.crawlContainers,
            host_namespace=args.namespace,
            plugin_places=args.plugin_places,
            frequency=args.frequency,
            options=options)
    else:
        raise NotImplementedError('Invalid crawlmode')

    worker = Worker(emitters=emitters,
                    frequency=args.frequency,
                    crawler=crawler)

    try:
        worker.run()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
