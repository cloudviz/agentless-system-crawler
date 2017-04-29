import cStringIO
import gzip
import unittest
import time
import os
import json

import mock
import requests.exceptions
import plugins_manager

from base_crawler import BaseFrame
from capturing import Capturing
from emitters_manager import EmittersManager
from plugins.emitters.file_emitter import FileEmitter
from plugins.emitters.base_http_emitter import BaseHttpEmitter
from plugins.emitters.http_emitter import HttpEmitter
from plugins.emitters.https_emitter import HttpsEmitter
from plugins.emitters.sas_emitter import SasEmitter
from plugins.emitters.kafka_emitter import KafkaEmitter
from plugins.emitters.mtgraphite_emitter import MtGraphiteEmitter
from plugins.emitters.fluentd_emitter import FluentdEmitter
from utils import crawler_exceptions


def mocked_formatter(frame):
    iostream = cStringIO.StringIO()
    iostream.write('namespace777.dummy-feature.test2 12345 14804\r\n')
    iostream.write('namespace777.dummy-feature.test2 12345 14805\r\n')
    return iostream


def mocked_formatter1(frame):
    iostream = cStringIO.StringIO()
    iostream.write('abc\r\n')
    iostream.write('def\r\n')
    return iostream

def mocked_formatter2(frame):
    iostream = cStringIO.StringIO()
    metadata = {}
    metadata["timestamp"] = "current-time"
    metadata["namespace"] = "my/name"
    metadata["features"] = "os,cpu,memory"
    metadata["source_type"] = "container"

    iostream.write('%s\t%s\t%s\n' %
                   ('metadata', json.dumps('metadata'),
                    json.dumps(metadata, separators=(',', ':'))))
    return iostream

def mocked_get_sas_token():
    return ('sas-token', 'cloudoe', 'access-group')

class RandomKafkaException(Exception):
        pass

def raise_value_error(*args, **kwargs):
        raise ValueError()

def mock_call_with_retries(function, max_retries=10,
                           exception_type=Exception,
                           _args=(), _kwargs={}):
    return function(*_args, **_kwargs)


def mocked_requests_post(*args, **kwargs):
    class MockResponse:

        def __init__(self, status_code):
            self.status_code = status_code
            self.text = 'blablableble'

        def json(self):
            return self.json_data
    if args[0] == 'http://1.1.1.1/good' or args[0] == 'https://1.1.1.1/good':
        return MockResponse(status_code=200)
    elif args[0] == 'http://1.1.1.1/bad' or args[0] == 'https://1.1.1.1/bad':
        return MockResponse(status_code=500)
    elif args[0] == 'http://1.1.1.1/exception' or args[0] == 'https://1.1.1.1/exception':
        raise requests.exceptions.RequestException('bla')
    elif args[0] == 'http://1.1.1.1/encoding_error' or args[0] == 'https://1.1.1.1/encoding_error':
        raise requests.exceptions.ChunkedEncodingError('bla')


class MockProducer:

    def __init__(self):
        self._produced = []

    def produce(self, msgs=[]):
        self._produced.extend(msgs)


def MockedKafkaConnect(self, broker, topic):
    self.producer = MockProducer()


class MockedMTGraphiteClient:

    def __init__(self, url):
        pass

    def send_messages(self, messages):
        return 1


class MockFluentdSender:

    def __init__(self):
        self._emitted = dict()

    def emit_with_time(self, tag, timestamp, item):
        self._emitted.update(item)
        self.last_error = None

    def clear_last_error():
        pass


def mocked_fluentd_connect(self, host, port):
    self.fluentd_sender = MockFluentdSender()


class EmitterTests(unittest.TestCase):
    image_name = 'alpine:latest'

    def setUp(self):
        plugins_manager.emitter_plugins = []
        pass

    def tearDown(self):
        pass

    def _test_emitter_csv_simple_stdout(self, compress=False):
        emitter = EmittersManager(urls=['stdout://'],
                                  compress=compress)
        frame = BaseFrame(feature_types=['os'])
        frame.add_features([("dummy_feature",
                             {'test': 'bla',
                              'test2': 12345,
                              'test3': 12345.0,
                              'test4': 12345.00000},
                             'dummy_feature')])
        emitter.emit(frame, 0)

    def test_emitter_csv_simple_stdout(self):
        with Capturing() as _output:
            self._test_emitter_csv_simple_stdout()
        output = "%s" % _output
        print _output
        assert len(_output) == 2
        assert "dummy_feature" in output
        assert "metadata" in output

    def test_emitter_csv_compressed_stdout(self):
        with Capturing() as _output:
            self._test_emitter_csv_simple_stdout(compress=True)
        output = "%s" % _output
        assert 'metadata' not in output
        assert len(output) > 0

    def test_emitter_csv_simple_file(self):
        emitter = EmittersManager(urls=['file:///tmp/test_emitter'],
                                  compress=False)
        frame = BaseFrame(feature_types=['os'])
        frame.add_features([("dummy_feature",
                             {'test': 'bla',
                              'test2': 12345,
                              'test3': 12345.0,
                              'test4': 12345.00000},
                             'dummy_feature')])
        emitter.emit(frame, 0)
        with open('/tmp/test_emitter.0') as f:
            _output = f.readlines()
            output = "%s" % _output
            print output
            assert len(_output) == 2
            assert "dummy_feature" in output
            assert "metadata" in output

    def test_emitter_all_features_compressed_csv(self):
        emitter = EmittersManager(urls=['file:///tmp/test_emitter'],
                                  compress=True)
        frame = BaseFrame(feature_types=[])
        frame.add_feature("memory", {'test3': 12345}, 'memory')
        frame.add_feature("memory_0", {'test3': 12345}, 'memory')
        frame.add_feature("load", {'load': 12345}, 'load')
        frame.add_feature("cpu", {'test3': 12345}, 'cpu')
        frame.add_feature("cpu_0", {'test3': 12345}, 'cpu')
        frame.add_feature("eth0", {'if_tx': 12345}, 'interface')
        frame.add_feature("eth0", {'if_rx': 12345}, 'interface')
        frame.add_feature("bla/bla", {'ble/ble': 12345}, 'disk')
        emitter.emit(frame, 0)
        with gzip.open('/tmp/test_emitter.0.gz') as f:
            _output = f.readlines()
            output = "%s" % _output
            print output
            assert len(_output) == 9
            assert "metadata" in output

    def test_emitter_all_features_csv(self):
        emitter = EmittersManager(urls=['file:///tmp/test_emitter'])
        frame = BaseFrame(feature_types=[])
        frame.add_feature("memory", {'test3': 12345}, 'memory')
        frame.add_feature("memory_0", {'test3': 12345}, 'memory')
        frame.add_feature("load", {'load': 12345}, 'load')
        frame.add_feature("cpu", {'test3': 12345}, 'cpu')
        frame.add_feature("cpu_0", {'test3': 12345}, 'cpu')
        frame.add_feature("eth0", {'if_tx': 12345}, 'interface')
        frame.add_feature("eth0", {'if_rx': 12345}, 'interface')
        frame.add_feature("bla/bla", {'ble/ble': 12345}, 'disk')
        emitter.emit(frame, 0)
        with open('/tmp/test_emitter.0') as f:
            _output = f.readlines()
            output = "%s" % _output
            print output
            assert len(_output) == 9
            assert "metadata" in output

    def test_emitter_all_features_graphite(self):
        emitter = EmittersManager(urls=['file:///tmp/test_emitter'],
                                  format='graphite')
        frame = BaseFrame(feature_types=[])
        frame.add_feature("memory", {'test3': 12345}, 'memory')
        frame.add_feature("memory_0", {'test3': 12345}, 'memory')
        frame.add_feature("load", {'load': 12345}, 'load')
        frame.add_feature("cpu", {'test3': 12345}, 'cpu')
        frame.add_feature("cpu_0", {'test3': 12345}, 'cpu')
        frame.add_feature("eth0", {'if_tx': 12345}, 'interface')
        frame.add_feature("eth0", {'if_rx': 12345}, 'interface')
        frame.add_feature("bla/bla", {'ble/ble': 12345}, 'disk')
        emitter.emit(frame, 0)
        with open('/tmp/test_emitter.0') as f:
            _output = f.readlines()
            output = "%s" % _output
            print output
            assert 'memory-0.test3 12345' in output
            assert len(_output) == 8

    def _test_emitter_graphite_simple_stdout(self):
        emitter = EmittersManager(urls=['stdout://'],
                                  format='graphite')
        frame = BaseFrame(feature_types=[])
        frame.metadata['namespace'] = 'namespace777'
        frame.add_features([("dummy_feature",
                             {'test': 'bla',
                              'test2': 12345,
                              'test3': 12345.0,
                              'test4': 12345.00000},
                             'dummy_feature')])
        emitter.emit(frame, 0)

    def test_emitter_graphite_simple_stdout(self):
        with Capturing() as _output:
            self._test_emitter_graphite_simple_stdout()
        output = "%s" % _output
        # should look like this:
        # ['namespace777.dummy-feature.test3 3.000000 1449870719',
        #  'namespace777.dummy-feature.test2 2.000000 1449870719',
        #  'namespace777.dummy-feature.test4 4.000000 1449870719']
        assert len(_output) == 3
        assert "dummy_feature" not in output  # can't have '_'
        assert "dummy-feature" in output  # can't have '_'
        assert "metadata" not in output
        assert 'namespace777.dummy-feature.test2' in output
        assert 'namespace777.dummy-feature.test3' in output
        assert 'namespace777.dummy-feature.test4' in output
        # three fields in graphite format
        assert len(_output[0].split(' ')) == 3
        # three fields in graphite format
        assert len(_output[1].split(' ')) == 3
        # three fields in graphite format
        assert len(_output[2].split(' ')) == 3
        assert float(_output[0].split(' ')[1]) == 12345.0
        assert float(_output[1].split(' ')[1]) == 12345.0
        assert float(_output[2].split(' ')[1]) == 12345.0

    def test_emitter_unsupported_format(self):
        metadata = {}
        metadata['namespace'] = 'namespace777'
        with self.assertRaises(
                crawler_exceptions.EmitterUnsupportedFormat):
            _ = EmittersManager(urls=['file:///tmp/test_emitter'],
                                format='unsupported')

    @mock.patch('plugins.emitters.file_emitter.FileEmitter.emit',
                side_effect=raise_value_error)
    def _test_emitter_failed_emit(self, *args):
        with self.assertRaises(ValueError):
            emitter = EmittersManager(urls=['file:///tmp/test_emitter'],
                                      format='csv')
            frame = BaseFrame(feature_types=[])
            frame.metadata['namespace'] = 'namespace777'
            frame.add_feature("memory", {'test3': 12345}, 'memory')
            emitter.emit(frame)

    def test_emitter_unsuported_protocol(self):
        with self.assertRaises(
                crawler_exceptions.EmitterUnsupportedProtocol):
            _ = EmittersManager(urls=['error:///tmp/test_emitter'],
                                format='graphite')

    def test_emitter_graphite_simple_file(self):
        emitter = EmittersManager(urls=['file:///tmp/test_emitter'],
                                  format='graphite')
        frame = BaseFrame(feature_types=[])
        frame.metadata['namespace'] = 'namespace777'
        frame.add_features([("dummy_feature",
                             {'test': 'bla',
                              'test2': 12345,
                              'test3': 12345.0,
                              'test4': 12345.00000},
                             'dummy_feature')])
        emitter.emit(frame)
        with open('/tmp/test_emitter.0') as f:
            _output = f.readlines()
            output = "%s" % _output
            # should look like this:
            # ['namespace777.dummy-feature.test3 3.000000 1449870719',
            #  'namespace777.dummy-feature.test2 2.000000 1449870719',
            #  'namespace777.dummy-feature.test4 4.000000 1449870719']
            assert len(_output) == 3
            assert "dummy_feature" not in output  # can't have '_'
            assert "dummy-feature" in output  # can't have '_'
            assert "metadata" not in output
            assert 'namespace777.dummy-feature.test2' in output
            assert 'namespace777.dummy-feature.test3' in output
            assert 'namespace777.dummy-feature.test4' in output
            # three fields in graphite format
            assert len(_output[0].split(' ')) == 3
            # three fields in graphite format
            assert len(_output[1].split(' ')) == 3
            # three fields in graphite format
            assert len(_output[2].split(' ')) == 3
            assert float(_output[0].split(' ')[1]) == 12345.0
            assert float(_output[1].split(' ')[1]) == 12345.0
            assert float(_output[2].split(' ')[1]) == 12345.0

    def test_emitter_json_simple_file(self):
        emitter = EmittersManager(urls=['file:///tmp/test_emitter'],
                                  format='json')
        frame = BaseFrame(feature_types=[])
        frame.metadata['namespace'] = 'namespace777'
        frame.add_features([("dummy_feature",
                             {'test': 'bla',
                              'test2': 12345,
                              'test3': 12345.0,
                              'test4': 12345.00000},
                             'dummy_feature')])
        emitter.emit(frame)
        with open('/tmp/test_emitter.0') as f:
            _output = f.readlines()
            output = "%s" % _output
            print output
            assert len(_output) == 2
            assert "metadata" not in output
            assert (
                '{"test3": 12345.0, "test2": 12345, "test4": 12345.0, '
                '"namespace": "namespace777", "test": "bla", "feature_type": '
                '"dummy_feature"}') in output

    def test_emitter_graphite_simple_compressed_file(self):
        emitter = EmittersManager(urls=['file:///tmp/test_emitter'],
                                  format='graphite',
                                  compress=True)
        frame = BaseFrame(feature_types=[])
        frame.metadata['namespace'] = 'namespace777'
        frame.add_features([("dummy_feature",
                             {'test': 'bla',
                              'test2': 12345,
                              'test3': 12345.0,
                              'test4': 12345.00000},
                             'dummy_feature')])
        emitter.emit(frame)
        with gzip.open('/tmp/test_emitter.0.gz') as f:
            _output = f.readlines()
            output = "%s" % _output
            # should look like this:
            # ['namespace777.dummy-feature.test3 3.000000 1449870719',
            #  'namespace777.dummy-feature.test2 2.000000 1449870719',
            #  'namespace777.dummy-feature.test4 4.000000 1449870719']
            assert len(_output) == 3
            assert "dummy_feature" not in output  # can't have '_'
            assert "dummy-feature" in output  # can't have '_'
            assert "metadata" not in output
            assert 'namespace777.dummy-feature.test2' in output
            assert 'namespace777.dummy-feature.test3' in output
            assert 'namespace777.dummy-feature.test4' in output
            # three fields in graphite format
            assert len(_output[0].split(' ')) == 3
            # three fields in graphite format
            assert len(_output[1].split(' ')) == 3
            # three fields in graphite format
            assert len(_output[2].split(' ')) == 3
            assert float(_output[0].split(' ')[1]) == 12345.0
            assert float(_output[1].split(' ')[1]) == 12345.0
            assert float(_output[2].split(' ')[1]) == 12345.0

    def test_emitter_base_http(self):
        emitter = BaseHttpEmitter()
        self.assertRaises(NotImplementedError, emitter.get_emitter_protocol)

    @mock.patch('iemit_plugin.IEmitter.format',
                side_effect=mocked_formatter)
    @mock.patch('plugins.emitters.base_http_emitter.requests.post',
                side_effect=mocked_requests_post)
    @mock.patch('plugins.emitters.base_http_emitter.time.sleep')
    def test_emitter_http(self, mock_sleep, mock_post, mock_format):
        emitter = HttpEmitter()
        emitter.init(url='http://1.1.1.1/good')
        emitter.emit('frame')
        self.assertEqual(mock_post.call_count, 1)

    @mock.patch('iemit_plugin.IEmitter.format',
                side_effect=mocked_formatter)
    @mock.patch('plugins.emitters.base_http_emitter.requests.post',
                side_effect=mocked_requests_post)
    @mock.patch('plugins.emitters.base_http_emitter.time.sleep')
    def test_emitter_http_server_error(self, mock_sleep, mock_post, mock_format):
        emitter = HttpEmitter()
        emitter.init(url='http://1.1.1.1/bad')
        emitter.emit('frame')
        self.assertEqual(mock_post.call_count, 5)

    @mock.patch('iemit_plugin.IEmitter.format',
                side_effect=mocked_formatter)
    @mock.patch('plugins.emitters.base_http_emitter.requests.post',
                side_effect=mocked_requests_post)
    @mock.patch('plugins.emitters.base_http_emitter.time.sleep')
    def test_emitter_http_request_exception(self, mock_sleep, mock_post, mock_format):
        emitter = HttpEmitter()
        emitter.init(url='http://1.1.1.1/exception')
        emitter.emit('frame')
        self.assertEqual(mock_post.call_count, 5)

    @mock.patch('iemit_plugin.IEmitter.format',
                side_effect=mocked_formatter)
    @mock.patch('plugins.emitters.base_http_emitter.requests.post',
                side_effect=mocked_requests_post)
    def test_emitter_http_encoding_error(self, mock_post, mock_format):
        emitter = HttpEmitter()
        emitter.init(url='http://1.1.1.1/encoding_error')
        emitter.emit('frame')
        # there are no retries for encoding errors
        self.assertEqual(mock_post.call_count, 1)

    @mock.patch('iemit_plugin.IEmitter.format',
                side_effect=mocked_formatter)
    @mock.patch('plugins.emitters.base_http_emitter.requests.post',
                side_effect=mocked_requests_post)
    @mock.patch('plugins.emitters.base_http_emitter.time.sleep')
    def test_emitter_https(self, mock_sleep, mock_post, mock_format):
        emitter = HttpsEmitter()
        emitter.init(url='https://1.1.1.1/good')
        emitter.emit('frame')
        self.assertEqual(mock_post.call_count, 1)

    @mock.patch('iemit_plugin.IEmitter.format',
                side_effect=mocked_formatter)
    @mock.patch('plugins.emitters.base_http_emitter.requests.post',
                side_effect=mocked_requests_post)
    @mock.patch('plugins.emitters.base_http_emitter.time.sleep')
    def test_emitter_https_server_error(self, mock_sleep, mock_post, mock_format):
        emitter = HttpsEmitter()
        emitter.init(url='https://1.1.1.1/bad')
        emitter.emit('frame')
        self.assertEqual(mock_post.call_count, 5)

    @mock.patch('iemit_plugin.IEmitter.format',
                side_effect=mocked_formatter)
    @mock.patch('plugins.emitters.base_http_emitter.requests.post',
                side_effect=mocked_requests_post)
    @mock.patch('plugins.emitters.base_http_emitter.time.sleep')
    def test_emitter_https_request_exception(self, mock_sleep, mock_post, mock_format):
        emitter = HttpsEmitter()
        emitter.init(url='https://1.1.1.1/exception')
        emitter.emit('frame')
        self.assertEqual(mock_post.call_count, 5)

    @mock.patch('iemit_plugin.IEmitter.format',
                side_effect=mocked_formatter)
    @mock.patch('plugins.emitters.base_http_emitter.requests.post',
                side_effect=mocked_requests_post)
    def test_emitter_https_encoding_error(self, mock_post, mock_format):
        emitter = HttpsEmitter()
        emitter.init(url='https://1.1.1.1/encoding_error')
        emitter.emit('frame')
        # there are no retries for encoding errors
        self.assertEqual(mock_post.call_count, 1)

    @mock.patch('plugins.emitters.sas_emitter.SasEmitter.get_sas_tokens',
                side_effect=mocked_get_sas_token)
    @mock.patch('iemit_plugin.IEmitter.format',
                side_effect=mocked_formatter2)
    @mock.patch('plugins.emitters.sas_emitter.requests.post',
                side_effect=mocked_requests_post)
    @mock.patch('plugins.emitters.base_http_emitter.time.sleep')
    def test_emitter_sas(self, mock_sleep, mock_post, mock_format, mock_get_sas_token):
        #env = SasEnvironment()
        emitter = SasEmitter()
        emitter.init(url='sas://1.1.1.1/good')
        emitter.emit('frame')
        self.assertEqual(mock_post.call_count, 1)

    @mock.patch('plugins.emitters.sas_emitter.SasEmitter.get_sas_tokens',
                side_effect=mocked_get_sas_token)
    @mock.patch('iemit_plugin.IEmitter.format',
                side_effect=mocked_formatter2)
    @mock.patch('plugins.emitters.sas_emitter.requests.post',
                side_effect=mocked_requests_post)
    @mock.patch('plugins.emitters.base_http_emitter.time.sleep')
    def test_emitter_sas_server_error(self, mock_sleep, mock_post, mock_format, mock_get_sas_token):
        #env = SasEnvironment()
        emitter = SasEmitter()
        emitter.init(url='sas://1.1.1.1/bad')
        emitter.emit('frame')
        self.assertEqual(mock_post.call_count, 5)

    @mock.patch('plugins.emitters.sas_emitter.SasEmitter.get_sas_tokens',
                side_effect=mocked_get_sas_token)
    @mock.patch('iemit_plugin.IEmitter.format',
                side_effect=mocked_formatter2)
    @mock.patch('plugins.emitters.sas_emitter.requests.post',
                side_effect=mocked_requests_post)
    @mock.patch('plugins.emitters.base_http_emitter.time.sleep')
    def test_emitter_sas_request_exception(self, mock_sleep, mock_post, mock_format, mock_get_sas_token):
        #env = SasEnvironment()
        emitter = SasEmitter()
        emitter.init(url='sas://1.1.1.1/exception')
        emitter.emit('frame')
        self.assertEqual(mock_post.call_count, 5)

    @mock.patch('plugins.emitters.sas_emitter.SasEmitter.get_sas_tokens',
                side_effect=mocked_get_sas_token)
    @mock.patch('iemit_plugin.IEmitter.format',
                side_effect=mocked_formatter2)
    @mock.patch('plugins.emitters.sas_emitter.requests.post',
                side_effect=mocked_requests_post)
    def test_emitter_sas_encoding_error(self, mock_post, mock_format, mocked_get_sas_token):
        #env = SasEnvironment()
        emitter = SasEmitter()
        emitter.init(url='sas://1.1.1.1/encoding_error')
        emitter.emit('frame')
        # there are no retries for encoding errors
        self.assertEqual(mock_post.call_count, 1)

    @mock.patch('plugins.emitters.kafka_emitter.KafkaEmitter.connect_to_broker',
                side_effect=MockedKafkaConnect, autospec=True)
    @mock.patch('plugins.emitters.kafka_emitter.KafkaEmitter.format',
                side_effect=mocked_formatter1)
    def test_emitter_kafka(self, *args):
        emitter = KafkaEmitter()
        emitter.init(url='kafka://1.1.1.1:123/topic1')
        emitter.emit('frame')
        assert emitter.producer._produced == ['abc\r\ndef\r\n']

    @mock.patch('plugins.emitters.kafka_emitter.KafkaEmitter.connect_to_broker',
                side_effect=MockedKafkaConnect, autospec=True)
    @mock.patch('plugins.emitters.kafka_emitter.KafkaEmitter.format',
                side_effect=mocked_formatter1)
    def test_emitter_kafka_one_per_line(self, *args):
        emitter = KafkaEmitter()
        emitter.init(url='kafka://1.1.1.1:123/topic1')
        emitter.emit_per_line = True
        emitter.emit('frame')
        assert set(emitter.producer._produced) == set(['abc\r\n', 'def\r\n'])

    @mock.patch('plugins.emitters.mtgraphite_emitter.MTGraphiteClient',
                side_effect=MockedMTGraphiteClient, autospec=True)
    @mock.patch('plugins.emitters.mtgraphite_emitter.MtGraphiteEmitter.format',
                side_effect=mocked_formatter)
    def test_emitter_mtgraphite(self, MockMTGraphiteClient, mocked_formatter):
        emitter = MtGraphiteEmitter()
        emitter.init(url='mtgraphite://1.1.1.1:123/topic1',
                     max_retries=0)
        emitter.emit('frame')
        assert MockMTGraphiteClient.call_count == 1

    @mock.patch('plugins.emitters.fluentd_emitter.FluentdEmitter.connect_to_fluentd_engine',
                side_effect=mocked_fluentd_connect, autospec=True)
    def test_emitter_fluentd_one_per_line(self, *args):
        frame = BaseFrame(feature_types=[])
        frame.metadata['namespace'] = 'namespace777'
        frame.metadata['timestamp'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
        frame.add_features([("dummy_feature_key",
                             {'test': 'bla',
                              'test2': 12345,
                              'test3': 12345.0,
                              'test4': 12345.00000},
                             'dummy_feature_type')])
        emitter = FluentdEmitter()
        emitter.init(url='fluentd://1.1.1.1:123', emit_format='json')
        emitter.emit_per_line = True
        emitter.emit(frame)
        emitted_json = emitter.fluentd_sender._emitted
        assert emitted_json["feature_key"] == "dummy_feature_key"
        assert emitted_json["feature_type"] == "dummy_feature_type"
        assert emitted_json["feature_val"] == {'test': 'bla',
                                               'test2': 12345,
                                               'test3': 12345.0,
                                               'test4': 12345.00000}

    @mock.patch('plugins.emitters.fluentd_emitter.FluentdEmitter.connect_to_fluentd_engine',
                side_effect=mocked_fluentd_connect, autospec=True)
    def test_emitter_fluentd(self, *args):
        frame = BaseFrame(feature_types=[])
        frame.metadata['namespace'] = 'namespace777'
        frame.metadata['timestamp'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
        frame.add_features([("dummy_feature_key",
                             {'test': 'bla',
                              'test2': 12345,
                              'test3': 12345.0,
                              'test4': 12345.00000},
                             'dummy_feature_type')])
        emitter = FluentdEmitter()
        emitter.init(url='fluentd://1.1.1.1:123', emit_format='json')
        emitter.emit_per_line = False
        emitter.emit(frame)
        emitted_json = emitter.fluentd_sender._emitted
        print emitted_json
        assert emitted_json["feature1"]["feature_key"] == "dummy_feature_key"
        assert emitted_json["feature1"]["feature_type"] == "dummy_feature_type"
        assert emitted_json["feature1"]["feature_val"] == {'test': 'bla',
                                                           'test2': 12345,
                                                           'test3': 12345.0,
                                                           'test4': 12345.00000}

    def test_emitter_logstash_simple_file(self):
        emitter = EmittersManager(urls=['file:///tmp/test_emitter'],
                                  format='logstash')
        frame = BaseFrame(feature_types=[])
        frame.metadata['namespace'] = 'namespace777'
        frame.add_features([("dummy_feature",
                             {'test': 'dummy',
                              'test2': 12345,
                              'test3': 12345.0,
                              'test4': 12345.00000},
                             'dummy_feature')])
        emitter.emit(frame)
        import json
        with open('/tmp/test_emitter.0') as f:
            output = json.load(f)
            assert len(output) == 2
            assert 'metadata' in output
            assert 'dummy_feature' in output
            assert type(output.get('dummy_feature')) == dict
