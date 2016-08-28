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
import Queue
from crawler_exceptions import (EmitterUnsupportedFormat,
                                EmitterUnsupportedProtocol,
                                EmitterBadURL,
                                EmitterEmitTimeout)
# External dependencies that must be pip install'ed separately

import kafka as kafka_python
import pykafka
import requests

from misc import NullHandler

logger = logging.getLogger('crawlutils')
# Kafka logs too much
logging.getLogger('kafka').addHandler(NullHandler())

def kafka_send(kurl, temp_fpath, format, topic, queue=None):
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
            raise EmitterUnsupportedFormat('Unsupported format: %s' % format)

        queue and queue.put((True, None))
    except Exception as e:
        if queue:
            queue.put((False, e))
        else:
            raise
    finally:
        queue and queue.close()

class Emitter:

    """Class that abstracts the outputs supported by the crawler, like
    stdout, or kafka.

    An object of this class is created for every frame emitted. A frame is
    emitted for every container and at every crawling interval.
    """

    # We want to use a global to store the MTGraphite client class so it
    # persists across metric intervals.

    mtgclient = None

    kafka_timeout_secs = 30

    # Debugging TIP: use url='file://<local-file>' to emit the frame data into
    # a local file

    def __init__(
        self,
        urls,
        emitter_args={},
        format='csv',
        max_emit_retries=9,
        kafka_timeout_secs=30
    ):

        self.urls = urls
        self.emitter_args = emitter_args
        self.compress = emitter_args.get('compress', False)
        self.format = format
        self.max_emit_retries = max_emit_retries
        self.mtgclient = None
        self.kafka_timeout_secs = kafka_timeout_secs

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

    def emit_dict_as_graphite(
        self,
        sysname,
        group,
        suffix,
        data,
        timestamp=None,
    ):
        timestamp = int(timestamp or time.time())
        items = data.items()

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

    def _emit_metadata_feature(self):
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
        if self.format == 'csv' or self.format == 'json':
            self.csv_writer.writerow(
                ['metadata',
                 json.dumps('metadata'),
                 json.dumps(metadata,
                            separators=(',', ':'))])
            self.num_features += 1

    def emit(
        self,
        feature_key,
        feature_val,
        feature_type=None,
    ):

        if self.num_features == 0:
            self._emit_metadata_feature()

        if isinstance(feature_val, dict):
            feature_val_as_dict = feature_val
        else:
            feature_val_as_dict = feature_val._asdict()

        if 'extra' in self.emitter_args and self.emitter_args['extra'] \
                and 'extra_all_features' in self.emitter_args \
                and self.emitter_args['extra_all_features']:
            feature_val_as_dict.update(json.loads(self.emitter_args['extra'
                                                                    ]))
        if self.format == 'csv' or self.format == 'json':
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
            raise EmitterUnsupportedFormat(
                'Unsupported format: %s' % self.format)
        self.num_features += 1

    def _close_file(self):

        # close the output file

        self.emitfile.close()

    def _publish_to_stdout(self):
        if self.format == 'json':
            raise NotImplementedError('json format is not supported')
        with open(self.temp_fpath, 'r') as fd:
            if self.compress:
                print '%s' % fd.read()
            else:
                for line in fd.readlines():
                    print line.strip()
                    sys.stdout.flush()

    def __make_http_post(self, url, headers, payload, max_emit_retries):
        for attempt in range(max_emit_retries):
            try:
                response = requests.post(url, headers=headers,
                                         params=self.emitter_args,
                                         data=payload)
            except requests.exceptions.ChunkedEncodingError as e:
                logger.exception(e)
                logger.error(
                    "POST to %s resulted in exception (attempt %d of %d), "
                    "will not re-try" % (url, attempt + 1, max_emit_retries))
                break
            except requests.exceptions.RequestException as e:
                logger.exception(e)
                logger.error(
                    "POST to %s resulted in exception (attempt %d of %d)" %
                    (url, attempt + 1, max_emit_retries))
                time.sleep(2.0 ** attempt * 0.1)
                continue
            if response.status_code != requests.codes.ok:
                logger.error("POST to %s resulted in status code %s: %s "
                             "(attempt %d of %d)" %
                             (url, str(response.status_code),
                              response.text, attempt + 1, max_emit_retries))
                time.sleep(2.0 ** attempt * 0.1)
            else:
                break

    def _publish_to_http(self, url, max_emit_retries=5):
        namespace = None
        headers = {}
        if self.compress:
            headers['content-encoding'] = 'gzip'
        with open(self.temp_fpath, 'rb') as framefp:
            if self.format == 'json':
                headers = {'content-type': 'application/json'}
                for feature in framefp:
                    feature_parts = feature.split()
                    if len(feature_parts) < 3:
                        logger.error(
                            "Invalid feature data found. %s %d" %
                            (feature_parts, len(feature_parts)))
                        continue

                    feature_name = feature_parts[0]
                    feature_value = feature_parts[1].strip("\"")

                    feature_data = json.loads("".join(feature_parts[2:]))

                    if feature_name == "metadata":
                        namespace = feature_data.get('namespace', None)
                    else:
                        feature_data['namespace'] = namespace
                    feature_data[feature_name] = feature_value
                    payload = json.dumps(feature_data)
                    self.__make_http_post(
                        url, headers, payload, max_emit_retries)

            elif self.format == 'csv' or self.format == 'graphite':
                headers = {'content-type': 'application/csv'}
                self.__make_http_post(url, headers, framefp, max_emit_retries)
            else:
                raise EmitterUnsupportedFormat(
                    'Unsupported format: %s' % self.format)

    def _publish_to_kafka_no_retries(self, url):

        list = url[len('kafka://'):].split('/')

        if len(list) == 2:
            kurl, topic = list
        else:
            raise EmitterBadURL(
                'The kafka url provided does not seem to be valid: %s. '
                'It should be something like this: '
                'kafka://[ip|hostname]:[port]/[kafka_topic]. '
                'For example: kafka://1.1.1.1:1234/metrics' % url)

        queue = multiprocessing.Queue()
        try:
            try:
                child_process = multiprocessing.Process(
                    name='kafka-emitter', target=kafka_send, args=(
                        kurl, self.temp_fpath, self.format, topic, queue))
                child_process.start()
            except OSError:
                #queue.close() # closing queue in finally clause
                raise

            try:
                (result, child_exception) = queue.get(
                    timeout=self.kafka_timeout_secs)
            except Queue.Empty:
                child_exception = EmitterEmitTimeout()

            child_process.join(self.kafka_timeout_secs)

            if child_process.is_alive():
                errmsg = ('Timed out waiting for process %d to exit.' %
                          child_process.pid)
                #queue.close() # closing queue in finally clause
                os.kill(child_process.pid, 9)
                logger.error(errmsg)
                raise EmitterEmitTimeout(errmsg)

            if child_exception:
                raise child_exception
        finally:
            queue.close()

    def _publish_to_kafka(self, url, max_emit_retries=8):
        if self.format == 'json':
            raise NotImplementedError('json format is not supported')

        broker_alive = False
        retries = 0
        while not broker_alive and retries <= max_emit_retries:
            try:
                retries += 1
                self._publish_to_kafka_no_retries(url)
                broker_alive = True
            except Exception as e:
                logger.debug(
                    '_publish_to_kafka_no_retries {0}: {1}'.format(
                        url, e))
                if retries <= max_emit_retries:

                    # Wait for (2^retries * 100) milliseconds

                    wait_time = 2.0 ** retries * 0.1
                    logger.error(
                        'Could not connect to the kafka server at %s. Retry '
                        'in %f seconds.' % (url, wait_time))
                    time.sleep(wait_time)
                else:
                    raise e

    def _publish_to_mtgraphite(self, url):
        if self.format == 'json':
            raise NotImplementedError('json format is not supported')
        if not Emitter.mtgclient:
            Emitter.mtgclient = MTGraphiteClient(url)
        with open(self.temp_fpath, 'r') as fp:
            num_pushed_to_queue = \
                Emitter.mtgclient.send_messages(fp.readlines())
            logger.debug('Pushed %d messages to mtgraphite queue'
                         % num_pushed_to_queue)

    def _write_to_file(self, url):
        if self.format == 'json':
            raise NotImplementedError('json format is not supported')
        output_path = url[len('file://'):]
        if self.compress:
            output_path += '.gz'
        shutil.move(self.temp_fpath, output_path)

    def _publish(self, url):
        logger.debug('Emitting frame to {0}'.format(url))
        if url.startswith('stdout://'):
            self._publish_to_stdout()
        elif url.startswith('http://'):
            self._publish_to_http(url, self.max_emit_retries)
        elif url.startswith('file://'):
            self._write_to_file(url)
        elif url.startswith('kafka://'):
            self._publish_to_kafka(url, self.max_emit_retries)
        elif url.startswith('mtgraphite://'):
            self._publish_to_mtgraphite(url)
        else:
            if os.path.exists(self.temp_fpath):
                os.remove(self.temp_fpath)
            raise EmitterUnsupportedProtocol(
                'Unsupported URL protocol {0}'.format(url))

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
            raise exc

        try:
            self._close_file()
            for url in self.urls:
                try:
                    self._publish(url)
                except EmitterEmitTimeout as exc:
                    logger.warning("Failed to emit due to timout, continuing anyway...")
        finally:
            if os.path.exists(self.temp_fpath):
                os.remove(self.temp_fpath)

        self.end_time = time.time()
        elapsed_time = self.end_time - self.begin_time
        logger.info(
            'Emitted {0} features in {1} seconds'.format(
                self.num_features,
                elapsed_time))
