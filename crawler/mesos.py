#! /usr/bin/python
# Copyright 2015 Ray Rodriguez

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import urllib2
import logging
import logging.handlers
import collections
import os

logger = None
PREFIX = "mesos-master"
MESOS_INSTANCE = ""
MESOS_HOST = "localhost"
MESOS_PORT = 5050
MESOS_VERSION = "0.22.0"
MESOS_URL = ""
VERBOSE_LOGGING = False

CONFIGS = []

Stat = collections.namedtuple('Stat', ('type', 'path'))

logger = logging.getLogger('crawlutils')


def configure_crawler_mesos(inurl):
    logger.debug('Mesos url %s' % inurl)
    CONFIGS.append({
        'mesos_url': inurl
    })


def fetch_stats(mesos_version):
    if CONFIGS == []:
        CONFIGS.append({
            'mesos_url': 'http://localhost:5050/metrics/snapshot'
        })
    logger.debug('connecting to %s' % CONFIGS[0]['mesos_url'])
    try:
        result = json.loads(
            urllib2.urlopen(CONFIGS[0]['mesos_url'], timeout=10).read())
    except urllib2.URLError:
        logger.exception('Exception opening mesos url %s', None)
        return None
    logger.debug('mesos_stats %s' % result)
    return result


def setup_logger(logger_name, logfile='crawler.log', process_id=None):
    _logger = logging.getLogger(logger_name)
    _logger.setLevel(logging.DEBUG)
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


def log_verbose(enabled, msg):
    if not enabled:
        return
    logger.debug('mesos-master plugin [verbose]: %s' % msg)


def snapshot_crawler_mesos_frame(inurl='http://localhost:9092'):
    setup_logger('crawler-mesos', 'crawler-mesos.log')
    mesos_version = MESOS_VERSION
    configure_crawler_mesos(inurl)

    return fetch_stats(mesos_version)
