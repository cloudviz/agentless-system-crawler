#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import logging
import tempfile
import gzip
import shutil
import time
import csv
import copy
import sys
from mtgraphite import MTGraphiteClient
import json
import multiprocessing

# External dependencies that must be pip install'ed separately

try:
    import kafka as kafka_python
    import pykafka
except ImportError:
    kafka_python = None
    pykafka = None

import requests

from features import (OSFeature, FileFeature, ConfigFeature, DiskFeature,
                      ProcessFeature, MetricFeature, ConnectionFeature,
                      PackageFeature, MemoryFeature, CpuFeature,
                      InterfaceFeature, LoadFeature, DockerPSFeature,
                      DockerHistoryFeature)
from misc import NullHandler


logger = logging.getLogger('crawlutils')


def kafka_send(kurl, temp_fpath, format, topic):
    try:
        kafka_python_client = kafka_python.KafkaClient(kurl)
        kafka_python_client.ensure_topic_exists(topic)
        kafka = pykafka.KafkaClient(hosts=kurl)

        publish_topic_object = kafka.topics[topic]
        # the default partitioner is random_partitioner
        producer = publish_topic_object.get_producer()

        if format == 'csv':
            with open(temp_fpath, 'r') as fp:
                text = fp.read()
                producer.produce([text])

        elif format == 'graphite':

            with open(temp_fpath, 'r') as fp:
                for line in fp.readlines():
                    producer.produce([line])
        else:
            raise
        sys.exit(0)
    except Exception as e:

        print e
        # kafka.close()
        sys.exit(1)


class Emitter:

    """Class that abstracts the outputs supported by the crawler, like
    stdout, or kafka.

    An object of this class is created for every frame emitted. A frame is
    emitted for every container and at every crawling interval.
    """

    # We want to use a global to store the MTGraphite client class so it
    # persists across metric intervals.

    mtgclient = None

    # Debugging TIP: use url='file://<local-file>' to emit the frame data into
    # a local file

    def __init__(
        self,
        urls,
        emitter_args={},
        format='csv',
        max_emit_retries=9,
    ):

        self.urls = urls
        self.emitter_args = emitter_args
        self.compress = emitter_args.get('compress', False)
        self.format = format
        self.max_emit_retries = max_emit_retries
        self.mtgclient = None

    def __enter__(self):
        (self.temp_fd, self.temp_fpath) = \
            tempfile.mkstemp(prefix='emit.')
        os.close(self.temp_fd)  # close temporary file descriptor

        # as we open immediately
        # need to find a better fix later

        if self.compress:
            self.emitfile = gzip.open(self.temp_fpath, 'wb')
        else:
            self.emitfile = open(self.temp_fpath, 'wb')
        self.csv_writer = csv.writer(self.emitfile, delimiter='\t',
                                     quotechar="'")
        self.begin_time = time.time()
        self.num_features = 0
        return self

    def _get_feature_type(self, feature):
        if isinstance(feature, OSFeature):
            return 'os'
        if isinstance(feature, FileFeature):
            return 'file'
        if isinstance(feature, ConfigFeature):
            return 'config'
        if isinstance(feature, DiskFeature):
            return 'disk'
        if isinstance(feature, ProcessFeature):
            return 'process'
        if isinstance(feature, ConnectionFeature):
            return 'connection'
        if isinstance(feature, MetricFeature):
            return 'metric'
        if isinstance(feature, PackageFeature):
            return 'package'
        if isinstance(feature, MemoryFeature):
            return 'memory'
        if isinstance(feature, CpuFeature):
            return 'cpu'
        if isinstance(feature, InterfaceFeature):
            return 'interface'
        if isinstance(feature, LoadFeature):
            return 'load'
        if isinstance(feature, DockerPSFeature):
            return 'dockerps'
        if isinstance(feature, DockerHistoryFeature):
            return 'dockerhistory'
        raise ValueError('Unrecognized feature type')

    def emit_dict_as_graphite(
        self,
        sysname,
        group,
        suffix,
        data,
        timestamp=None,
    ):
        timestamp = int(timestamp or time.time())
        try:
            items = data.items()
        except:
            return

        # this is for issue #343

        sysname = sysname.replace('/', '.')

        for (metric, value) in items:
            try:
                value = float(value)
            except Exception:

                # value was not a float or anything that looks like a float

                continue

            metric = metric.replace('(', '_').replace(')', '')
            metric = metric.replace(' ', '_').replace('-', '_')
            metric = metric.replace('/', '_').replace('\\', '_')

            suffix = suffix.replace('_', '-')
            if 'cpu' in suffix or 'memory' in suffix:
                metric = metric.replace('_', '-')
            if 'if' in metric:
                metric = metric.replace('_tx', '.tx')
                metric = metric.replace('_rx', '.rx')
            if suffix == 'load':
                suffix = 'load.load'
            suffix = suffix.replace('/', '$')

            tmp_message = '%s.%s.%s %f %d\r\n' % (sysname, suffix,
                                                  metric, value, timestamp)
            self.emitfile.write(tmp_message)
        return

    # Added optional feature_type so that we can bypass feature type discovery
    # for FILE crawlmode

    def emit(
        self,
        feature_key,
        feature_val,
        feature_type=None,
    ):

        # Add metadata as first feature

        if self.num_features == 0:
            try:
                metadata = copy.deepcopy(self.emitter_args)

                # Update timestamp to the actual emit time

                metadata['timestamp'] = \
                    time.strftime('%Y-%m-%dT%H:%M:%S%z')
                if 'extra' in metadata:
                    del metadata['extra']
                    if self.emitter_args['extra']:
                        metadata.update(json.loads(self.emitter_args['extra'
                                                                     ]))
                if 'extra_all_features' in metadata:
                    del metadata['extra_all_features']
                if self.format == 'csv':
                    self.csv_writer.writerow(
                        ['metadata',
                         json.dumps('metadata'),
                         json.dumps(metadata,
                                    separators=(',', ':'))])
                    self.num_features += 1
            except Exception as e:
                logger.exception(e)
                raise

        feature_type = feature_type or self._get_feature_type(feature_val)
        if isinstance(feature_val, dict):
            feature_val_as_dict = feature_val
        else:
            feature_val_as_dict = feature_val._asdict()
        if 'extra' in self.emitter_args and self.emitter_args['extra'] \
                and 'extra_all_features' in self.emitter_args \
                and self.emitter_args['extra_all_features'] == True:
            feature_val_as_dict.update(json.loads(self.emitter_args['extra'
                                                                    ]))
        try:
            if self.format == 'csv':
                self.csv_writer.writerow(
                    [feature_type,
                     json.dumps(feature_key),
                     json.dumps(feature_val_as_dict,
                                separators=(',', ':'))])
            elif self.format == 'graphite':
                if 'namespace' in self.emitter_args:
                    namespace = self.emitter_args['namespace']
                else:
                    namespace = 'undefined'
                self.emit_dict_as_graphite(
                    namespace,
                    feature_type,
                    feature_key,
                    feature_val_as_dict)
            else:
                raise Exception('Unsupported emitter format.')
            self.num_features += 1
        except Exception as e:
            logger.exception(e)
            raise

    def _close_file(self):

        # close the output file

        self.emitfile.close()

    def _publish_to_stdout(self):
        with open(self.temp_fpath, 'r') as fd:
            if self.compress:
                print fd.read()
            else:
                for line in fd.readlines():
                    print line.strip()
                    sys.stdout.flush()

    def _publish_to_broker(self, url, max_emit_retries=5):
        for attempt in range(max_emit_retries):
            try:
                headers = {'content-type': 'text/csv'}
                if self.compress:
                    headers['content-encoding'] = 'gzip'
                with open(self.temp_fpath, 'rb') as framefp:
                    response = requests.post(
                        url, headers=headers, params=self.emitter_args, data=framefp)
            except requests.exceptions.ChunkedEncodingError as e:
                logger.exception(e)
                logger.error("POST to %s resulted in exception (attempt %d of %d), will not re-try" %
                             (url, attempt + 1, max_emit_retries))
                break
            except requests.exceptions.RequestException as e:
                logger.exception(e)
                logger.error("POST to %s resulted in exception (attempt %d of %d)" % (
                    url, attempt + 1, max_emit_retries))
                time.sleep(2.0 ** attempt * 0.1)
                continue

            if response.status_code != requests.codes.ok:
                logger.error("POST to %s resulted in status code %s: %s (attempt %d of %d)" % (
                    url, str(response.status_code), response.text, attempt + 1, max_emit_retries))
                time.sleep(2.0 ** attempt * 0.1)
            else:
                break

    def _publish_to_kafka_no_retries(self, url):

        if kafka_python is None or pykafka is None:
            raise ImportError('Please install kafka and pykafka')

        try:
            list = url[len('kafka://'):].split('/')

            if len(list) == 2:
                kurl, topic = list
            else:
                raise Exception(
                    'The kafka url provided does not seem to be valid: %s. '
                    'It should be something like this: '
                    'kafka://[ip|hostname]:[port]/[kafka_topic]. '
                    'For example: kafka://1.1.1.1:1234/metrics' % url)

            h = NullHandler()
            logging.getLogger('kafka').addHandler(h)

            try:
                child_process = multiprocessing.Process(
                    name='kafka-emitter', target=kafka_send, args=(
                        kurl, self.temp_fpath, self.format, topic))
                child_process.start()
                child_process.join(120)
            except OSError:
                queue.close()
                raise

        except Exception as e:

            # kafka.close()

            logger.debug('Could not send data to {0}: {1}'.format(url,
                                                                  e))
            raise

    def _publish_to_mtgraphite(self, url):
        if not Emitter.mtgclient:
            Emitter.mtgclient = MTGraphiteClient(url)
        with open(self.temp_fpath, 'r') as fp:
            num_pushed_to_queue = \
                Emitter.mtgclient.send_messages(fp.readlines())
            logger.debug('Pushed %d messages to mtgraphite queue'
                         % num_pushed_to_queue)

    def _write_to_file(self, url):
        output_path = url[len('file://'):]
        if self.compress:
            output_path += '.gz'
        shutil.move(self.temp_fpath, output_path)

    def __exit__(
        self,
        typ,
        exc,
        trc,
    ):
        if exc:
            self._close_file()
            if os.path.exists(self.temp_fpath):
                os.remove(self.temp_fpath)
            return False
        try:
            self._close_file()
            for url in self.urls:
                logger.debug('Emitting frame to {0}'.format(url))
                if url.startswith('stdout://'):
                    self._publish_to_stdout()
                elif url.startswith('http://'):
                    self._publish_to_broker(url, self.max_emit_retries)
                elif url.startswith('file://'):
                    self._write_to_file(url)
                elif url.startswith('kafka://'):
                    self._publish_to_kafka(url, self.max_emit_retries)
                elif url.startswith('mtgraphite://'):
                    self._publish_to_mtgraphite(url)
                else:
                    if os.path.exists(self.temp_fpath):
                        os.remove(self.temp_fpath)
                    raise ValueError(
                        'Unsupported URL protocol {0}'.format(url))
        except Exception as e:
            logger.exception(e)
            raise
        finally:
            if os.path.exists(self.temp_fpath):
                os.remove(self.temp_fpath)
        self.end_time = time.time()
        elapsed_time = self.end_time - self.begin_time
        logger.info(
            'Emitted {0} features in {1} seconds'.format(
                self.num_features,
                elapsed_time))
        return False
