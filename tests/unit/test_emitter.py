from capturing import Capturing
import mock
import unittest
import docker
import requests.exceptions
import tempfile
import os
import shutil
import subprocess
import gzip
import zlib

import crawler.crawler_exceptions
from crawler.emitter import Emitter


def mocked_requests_post(*args, **kwargs):
    class MockResponse:

        def __init__(self, status_code):
            self.status_code = status_code
            self.text = 'blablableble'

        def json(self):
            return self.json_data
    if args[0] == 'http://1.1.1.1/good':
        return MockResponse(status_code=200)
    elif args[0] == 'http://1.1.1.1/bad':
        return MockResponse(status_code=500)
    elif args[0] == 'http://1.1.1.1/exception':
        raise requests.exceptions.RequestException('bla')
    elif args[0] == 'http://1.1.1.1/encoding_error':
        raise requests.exceptions.ChunkedEncodingError('bla')


def mocked_multiprocessing_process(name='', target='', args=''):
    raise OSError


class MockedKafkaClient1:

    def __init__(self, kurl):
        print 'kafka_python init'
        pass

    def ensure_topic_exists(self, topic):
        return True


class RandomKafkaException(Exception):
    pass


class MockProducer:

    def __init__(self, good=True, timeout=False):
        self.good = good
        self.timeout = timeout

    def produce(self, msgs=[]):
        print 'produce'
        if self.good:
            print msgs
        else:
            raise RandomKafkaException('random kafka exception')
        if self.timeout:
            while True:
                a = 1


class MockTopic:

    def __init__(self, good=True, timeout=False):
        self.good = good
        self.timeout = timeout

    def get_producer(self):
        print 'get producer'
        return MockProducer(good=self.good, timeout=self.timeout)


class MockedKafkaClient2:

    def __init__(self, hosts=[]):
        print 'pykafka init'
        self.topics = {'topic1': MockTopic(good=True),
                       'badtopic': MockTopic(good=False),
                       'timeouttopic': MockTopic(timeout=True)}


class MockedMTGraphiteClient:

    def __init__(self, url):
        pass

    def send_messages(self, messages):
        return 1


# TODO (ricarkol): It would be nice to avoid all side effects and mock all
# temp files being created.


class EmitterTests(unittest.TestCase):
    image_name = 'alpine:latest'

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def _test_emitter_csv_simple_stdout(self):
        with Emitter(urls=['stdout://']) as emitter:
            emitter.emit("dummy_feature",
                         {'test': 'bla',
                          'test2': 12345,
                          'test3': 12345.0,
                          'test4': 12345.00000},
                         'dummy_feature')

    def test_emitter_csv_simple_stdout(self):
        with Capturing() as _output:
            self._test_emitter_csv_simple_stdout()
        output = "%s" % _output
        assert len(_output) == 2
        assert "dummy_feature" in output
        assert "metadata" in output

    def test_emitter_csv_compressed_stdout(self):
        with Capturing() as _output:
            with Emitter(urls=['stdout://'],
                         emitter_args={'namespace': '123',
                                       'compress': True}) as emitter:
                emitter.emit("dummy", {'test': 'bla'}, 'dummy')
        output = "%s" % _output

    def test_emitter_csv_simple_file(self):
        with Emitter(urls=['file:///tmp/test_emitter'],
                     emitter_args={'namespace': 'bla'}) as emitter:
            emitter.emit("dummy_feature",
                         {'test': 'bla',
                          'test2': 12345,
                          'test3': 12345.0,
                          'test4': 12345.00000},
                         'dummy_feature')
        with open('/tmp/test_emitter') as f:
            _output = f.readlines()
            output = "%s" % _output
            assert len(_output) == 2
            assert "dummy_feature" in output
            assert "metadata" in output

    def test_emitter_all_features_compressed_csv(self):
        with Emitter(urls=['file:///tmp/test_emitter'],
                     emitter_args={'extra': '{"a":"1", "b":2}',
                                   'extra_all_features': True,
                                   'uuid': 'aaaaaa',
                                   'compress': True},
                     format='csv') as emitter:
            emitter.emit("memory", {'test3': 12345}, 'memory')
            emitter.emit("memory_0", {'test3': 12345}, 'memory')
            emitter.emit("load", {'load': 12345}, 'load')
            emitter.emit("cpu", {'test3': 12345}, 'cpu')
            emitter.emit("cpu_0", {'test3': 12345}, 'cpu')
            emitter.emit("eth0", {'if_tx': 12345}, 'interface')
            emitter.emit("eth0", {'if_rx': 12345}, 'interface')
            emitter.emit("bla/bla", {'ble/ble': 12345}, 'disk')
        with gzip.open('/tmp/test_emitter.gz') as f:
            _output = f.readlines()
            output = "%s" % _output
            print output
            assert len(_output) == 9
            assert "metadata" in output

    def test_emitter_all_features_csv(self):
        with Emitter(urls=['file:///tmp/test_emitter'],
                     emitter_args={'extra': '{"a":"1", "b":2}',
                                   'extra_all_features': True,
                                   'uuid': 'aaaaaa'},
                     format='csv') as emitter:
            emitter.emit("memory", {'test3': 12345}, 'memory')
            emitter.emit("memory_0", {'test3': 12345}, 'memory')
            emitter.emit("load", {'load': 12345}, 'load')
            emitter.emit("cpu", {'test3': 12345}, 'cpu')
            emitter.emit("cpu_0", {'test3': 12345}, 'cpu')
            emitter.emit("eth0", {'if_tx': 12345}, 'interface')
            emitter.emit("eth0", {'if_rx': 12345}, 'interface')
            emitter.emit("bla/bla", {'ble/ble': 12345}, 'disk')
        with open('/tmp/test_emitter') as f:
            _output = f.readlines()
            output = "%s" % _output
            print output
            assert len(_output) == 9
            assert "metadata" in output

    def test_emitter_all_features_graphite(self):
        with Emitter(urls=['file:///tmp/test_emitter'],
                     emitter_args={'extra': '{"a":"1", "b":2}',
                                   'extra_all_features': True,
                                   'uuid': 'aaaaaa'},
                     format='graphite') as emitter:
            emitter.emit("memory", {'test3': 12345}, 'memory')
            emitter.emit("memory_0", {'test3': 12345}, 'memory')
            emitter.emit("load", {'load': 12345}, 'load')
            emitter.emit("cpu", {'test3': 12345}, 'cpu')
            emitter.emit("cpu_0", {'test3': 12345}, 'cpu')
            emitter.emit("eth0", {'if_tx': 12345}, 'interface')
            emitter.emit("eth0", {'if_rx': 12345}, 'interface')
            emitter.emit("bla/bla", {'ble/ble': 12345}, 'disk')
        with open('/tmp/test_emitter') as f:
            _output = f.readlines()
            output = "%s" % _output
            print output
            assert len(_output) == 24

    # Tests the Emitter crawler class
    # Throws an AssertionError if any test fails
    def _test_emitter_graphite_simple_stdout(self):
        metadata = {}
        metadata['namespace'] = 'namespace777'
        with Emitter(urls=['stdout://'],
                     emitter_args=metadata,
                     format='graphite') as emitter:
            emitter.emit("dummy_feature",
                         {'test': 'bla',
                          'test2': 12345,
                          'test3': 12345.0,
                          'test4': 12345.00000},
                         'dummy_feature')

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
        try:
            with Emitter(urls=['file:///tmp/test_emitter'],
                         emitter_args=metadata,
                         format='unsupported') as emitter:
                emitter.emit("dummy_feature",
                             {'test': 'bla',
                              'test2': 12345,
                              'test3': 12345.0,
                              'test4': 12345.00000},
                             'dummy_feature')
        except crawler.crawler_exceptions.EmitterUnsupportedFormat:
            pass
        except Exception:
            raise

    def test_emitter_exception(self):
        emitter = Emitter(urls=['file:///tmp/test_emitter'],
                          emitter_args={'extra': '{"a2}',
                                        'extra_all_features': True,
                                        'uuid': 'aaaaaa'},
                          format='csv')
        emitter.__enter__()
        emitter.__exit__(None, ValueError('a'), None)

    def test_emitter_incorrect_json(self):
        try:
            with Emitter(urls=['file:///tmp/test_emitter'],
                         emitter_args={'extra': '{"a2}',
                                       'extra_all_features': True,
                                       'uuid': 'aaaaaa'},
                         format='csv') as emitter:
                emitter.emit("memory", {'test3': 12345}, 'memory')
        except ValueError:
            pass
        except Exception:
            raise

    def test_emitter_failed_emit(self):
        metadata = {}
        metadata['namespace'] = 'namespace777'
        try:
            with Emitter(urls=['file:///tmp/test_emitter'],
                         format='csv') as emitter:
                with mock.patch('crawler.emitter.json.dumps') as mock_dumps:
                    mock_dumps.side_effect = ValueError()
                    emitter.emit("memory", {'test3': 12345}, 'memory')
        except ValueError:
            pass
        except Exception:
            raise

    def test_emitter_unsuported_protocol(self):
        metadata = {}
        metadata['namespace'] = 'namespace777'
        try:
            with Emitter(urls=['error:///tmp/test_emitter'],
                         emitter_args=metadata,
                         format='graphite') as emitter:
                emitter.emit("dummy_feature",
                             {'test': 'bla',
                              'test2': 12345,
                              'test3': 12345.0,
                              'test4': 12345.00000},
                             'dummy_feature')
                emitter.emit("dummy_feature",
                             {'test': 'bla',
                              'test2': 12345,
                              'test3': 12345.0,
                              'test4': 12345.00000},
                             'dummy_feature')
        except crawler.crawler_exceptions.EmitterUnsupportedProtocol:
            pass
        except Exception:
            raise

    def test_emitter_graphite_simple_file(self):
        metadata = {}
        metadata['namespace'] = 'namespace777'
        with Emitter(urls=['file:///tmp/test_emitter'],
                     emitter_args=metadata,
                     format='graphite') as emitter:
            emitter.emit("dummy_feature",
                         {'test': 'bla',
                          'test2': 12345,
                          'test3': 12345.0,
                          'test4': 12345.00000},
                         'dummy_feature')
        with open('/tmp/test_emitter') as f:
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

    def test_emitter_graphite_invalid_feature(self):
        metadata = {}
        metadata['namespace'] = 'namespace777'
        with Emitter(urls=['file:///tmp/test_emitter'],
                     emitter_args=metadata,
                     format='graphite') as emitter:
            with self.assertRaises(AttributeError):
                emitter.emit("dummy", {'blabla'}, 'dummy')
            with self.assertRaises(AttributeError):
                emitter.emit("dummy", 12, 'dummy')

    def test_emitter_graphite_simple_compressed_file(self):
        metadata = {}
        metadata['namespace'] = 'namespace777'
        metadata['compress'] = True
        with Emitter(urls=['file:///tmp/test_emitter'],
                     emitter_args=metadata,
                     format='graphite') as emitter:
            emitter.emit("dummy_feature",
                         {'test': 'bla',
                          'test2': 12345,
                          'test3': 12345.0,
                          'test4': 12345.00000},
                         'dummy_feature')
        with gzip.open('/tmp/test_emitter.gz') as f:
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

    @mock.patch('crawler.emitter.requests.post',
                side_effect=mocked_requests_post)
    @mock.patch('crawler.emitter.time.sleep')
    def test_emitter_graphite_broker(self, mock_sleep, mock_post):
        metadata = {}
        metadata['namespace'] = 'namespace777'
        retries = 2
        with Emitter(urls=['http://1.1.1.1/good'],
                     emitter_args=metadata,
                     format='graphite',
                     max_emit_retries=retries) as emitter:
            emitter.emit("dummy_feature",
                         {'test': 'bla',
                          'test2': 12345,
                          'test3': 12345.0,
                          'test4': 12345.00000},
                         'dummy_feature')
            emitter.emit("dummy_feature",
                         {'test': 'bla',
                          'test2': 12345,
                          'test3': 12345.0,
                          'test4': 12345.00000},
                         'dummy_feature')
        self.assertEqual(mock_post.call_count, 1)

    @mock.patch('crawler.emitter.requests.post',
                side_effect=mocked_requests_post)
    @mock.patch('crawler.emitter.time.sleep')
    def test_emitter_graphite_broker_compress(self, mock_sleep, mock_post):
        metadata = {}
        metadata['namespace'] = 'namespace777'
        metadata['compress'] = True
        retries = 2
        with Emitter(urls=['http://1.1.1.1/good'],
                     emitter_args=metadata,
                     format='graphite',
                     max_emit_retries=retries) as emitter:
            emitter.emit("dummy_feature",
                         {'test': 'bla',
                          'test2': 12345,
                          'test3': 12345.0,
                          'test4': 12345.00000},
                         'dummy_feature')
            emitter.emit("dummy_feature",
                         {'test': 'bla',
                          'test2': 12345,
                          'test3': 12345.0,
                          'test4': 12345.00000},
                         'dummy_feature')
        self.assertEqual(mock_post.call_count, 1)

    @mock.patch('crawler.emitter.requests.post',
                side_effect=mocked_requests_post)
    @mock.patch('crawler.emitter.time.sleep')
    def test_emitter_graphite_broker_server_error(self, mock_sleep, mock_post):
        metadata = {}
        metadata['namespace'] = 'namespace777'
        retries = 2
        with Emitter(urls=['http://1.1.1.1/bad'],
                     emitter_args=metadata,
                     format='graphite',
                     max_emit_retries=retries) as emitter:
            emitter.emit("dummy_feature",
                         {'test': 'bla',
                          'test2': 12345,
                          'test3': 12345.0,
                          'test4': 12345.00000},
                         'dummy_feature')
            emitter.emit("dummy_feature",
                         {'test': 'bla',
                          'test2': 12345,
                          'test3': 12345.0,
                          'test4': 12345.00000},
                         'dummy_feature')
        self.assertEqual(mock_post.call_count, retries)

    @mock.patch('crawler.emitter.requests.post',
                side_effect=mocked_requests_post)
    @mock.patch('crawler.emitter.time.sleep')
    def test_emitter_graphite_broker_request_exception(
            self, mock_sleep, mock_post):
        metadata = {}
        metadata['namespace'] = 'namespace777'
        retries = 2
        with Emitter(urls=['http://1.1.1.1/exception'],
                     emitter_args=metadata,
                     format='graphite',
                     max_emit_retries=retries) as emitter:
            emitter.emit("dummy_feature",
                         {'test': 'bla',
                          'test2': 12345,
                          'test3': 12345.0,
                          'test4': 12345.00000},
                         'dummy_feature')
            emitter.emit("dummy_feature",
                         {'test': 'bla',
                          'test2': 12345,
                          'test3': 12345.0,
                          'test4': 12345.00000},
                         'dummy_feature')
        self.assertEqual(mock_post.call_count, retries)

    @mock.patch('crawler.emitter.requests.post',
                side_effect=mocked_requests_post)
    def test_emitter_graphite_broker_encoding_error(self, mock_post):
        metadata = {}
        metadata['namespace'] = 'namespace777'
        retries = 10
        with Emitter(urls=['http://1.1.1.1/encoding_error'],
                     emitter_args=metadata,
                     format='graphite',
                     max_emit_retries=retries) as emitter:
            emitter.emit("dummy_feature",
                         {'test': 'bla',
                          'test2': 12345,
                          'test3': 12345.0,
                          'test4': 12345.00000},
                         'dummy_feature')
            emitter.emit("dummy_feature",
                         {'test': 'bla',
                          'test2': 12345,
                          'test3': 12345.0,
                          'test4': 12345.00000},
                         'dummy_feature')
        # there are no retries for encoding errors
        self.assertEqual(mock_post.call_count, 1)

    @mock.patch('crawler.emitter.pykafka.KafkaClient',
                side_effect=MockedKafkaClient2, autospec=True)
    @mock.patch('crawler.emitter.kafka_python.KafkaClient',
                side_effect=MockedKafkaClient1, autospec=True)
    def test_emitter_csv_kafka_invalid_url(
            self, MockKafkaClient1, MockKafkaClient2):
        metadata = {}
        metadata['namespace'] = 'namespace777'
        with self.assertRaises(crawler.crawler_exceptions.EmitterBadURL):
            with Emitter(urls=['kafka://abc'], max_emit_retries=1) as emitter:
                emitter.emit("dummy_feature", {'test': 'bla'}, 'dummy_feature')

    @mock.patch('crawler.emitter.pykafka.KafkaClient',
                side_effect=MockedKafkaClient2, autospec=True)
    @mock.patch('crawler.emitter.kafka_python.KafkaClient',
                side_effect=MockedKafkaClient1, autospec=True)
    @mock.patch('crawler.emitter.time.sleep')
    def test_emitter_csv_kafka(
            self, mock_sleep, MockKafkaClient1, MockKafkaClient2):
        metadata = {}
        metadata['namespace'] = 'namespace777'
        retries = 2
        with Emitter(urls=['kafka://1.1.1.1:123/topic1'],
                     emitter_args=metadata,
                     max_emit_retries=retries) as emitter:
            emitter.emit("dummy_feature",
                         {'test': 'bla',
                          'test2': 12345,
                          'test3': 12345.0,
                          'test4': 12345.00000},
                         'dummy_feature')
        # XXX: MockKafkaClient1.call_count won't have the desifed effect and
        # will be 0 because it is called from another process. So, let's just
        # call the function and make sure no exception is thrown.

    @mock.patch('crawler.emitter.pykafka.KafkaClient',
                side_effect=MockedKafkaClient2, autospec=True)
    @mock.patch('crawler.emitter.kafka_python.KafkaClient',
                side_effect=MockedKafkaClient1, autospec=True)
    @mock.patch('crawler.emitter.time.sleep')
    def test_emitter_graphite_kafka(
            self, mock_sleep, MockKafkaClient1, MockKafkaClient2):
        metadata = {}
        metadata['namespace'] = 'namespace777'
        retries = 2
        with Emitter(urls=['kafka://1.1.1.1:123/topic1'],
                     emitter_args=metadata,
                     format='graphite',
                     max_emit_retries=retries) as emitter:
            emitter.emit("dummy_feature",
                         {'test': 'bla',
                          'test2': 12345,
                          'test3': 12345.0,
                          'test4': 12345.00000},
                         'dummy_feature')
        # XXX: MockKafkaClient1.call_count won't have the desifed effect and
        # will be 0 because it is called from another process. So, let's just
        # call the function and make sure no exception is thrown.

    @mock.patch('crawler.emitter.pykafka.KafkaClient',
                side_effect=MockedKafkaClient2, autospec=True)
    @mock.patch('crawler.emitter.kafka_python.KafkaClient',
                side_effect=MockedKafkaClient1, autospec=True)
    @mock.patch('crawler.emitter.time.sleep')
    def test_emitter_csv_kafka_failed_emit(self, mock_sleep, MockC1, MockC2):
        metadata = {}
        metadata['namespace'] = 'namespace777'
        retries = 2
        with self.assertRaises(RandomKafkaException):
            with Emitter(urls=['kafka://1.1.1.1:123/badtopic'],
                         emitter_args=metadata,
                         max_emit_retries=retries) as emitter:
                emitter.emit("dummy_feature",
                             {'test': 'bla',
                              'test2': 12345,
                              'test3': 12345.0,
                              'test4': 12345.00000},
                             'dummy_feature')

    @mock.patch('crawler.emitter.pykafka.KafkaClient',
                side_effect=MockedKafkaClient2, autospec=True)
    @mock.patch('crawler.emitter.kafka_python.KafkaClient',
                side_effect=MockedKafkaClient1, autospec=True)
    @mock.patch('crawler.emitter.time.sleep')
    def test_emitter_csv_kafka_unsupported_format(
            self, mock_sleep, MockC1, MockC2):
        metadata = {}
        metadata['namespace'] = 'namespace777'
        retries = 2
        with self.assertRaises(crawler.crawler_exceptions.EmitterUnsupportedFormat):
            with Emitter(urls=['kafka://1.1.1.1:123/badtopic'],
                         emitter_args=metadata,
                         format='blablafformat',
                         max_emit_retries=retries) as emitter:
                emitter.emit("dummy_feature",
                             {'test': 'bla',
                              'test2': 12345,
                              'test3': 12345.0,
                              'test4': 12345.00000},
                             'dummy_feature')

    @mock.patch('crawler.emitter.pykafka.KafkaClient',
                side_effect=MockedKafkaClient2, autospec=True)
    @mock.patch('crawler.emitter.kafka_python.KafkaClient',
                side_effect=MockedKafkaClient1, autospec=True)
    def test_emitter_csv_kafka_failed_emit_no_retries(self, MockC1, MockC2):
        metadata = {}
        metadata['namespace'] = 'namespace777'
        retries = 1
        with self.assertRaises(RandomKafkaException):
            with Emitter(urls=['kafka://1.1.1.1:123/badtopic'],
                         emitter_args=metadata,
                         max_emit_retries=retries) as emitter:
                emitter.emit("dummy_feature",
                             {'test': 'bla',
                              'test2': 12345,
                              'test3': 12345.0,
                              'test4': 12345.00000},
                             'dummy_feature')

    @mock.patch('crawler.emitter.pykafka.KafkaClient',
                side_effect=MockedKafkaClient2, autospec=True)
    @mock.patch('crawler.emitter.kafka_python.KafkaClient',
                side_effect=MockedKafkaClient1, autospec=True)
    @mock.patch('crawler.emitter.time.sleep')
    def test_emitter_csv_kafka_emit_timeout(self, mock_sleep, MockC1, MockC2):
        metadata = {}
        metadata['namespace'] = 'namespace777'
        retries = 2
        with self.assertRaises(crawler.crawler_exceptions.EmitterEmitTimeout):
            with Emitter(urls=['kafka://1.1.1.1:123/timeouttopic'],
                         emitter_args=metadata,
                         max_emit_retries=retries,
                         kafka_timeout_secs=0.1) as emitter:
                emitter.emit("dummy", {'test': 'bla'}, 'dummy')

    @mock.patch(
        'crawler.emitter.multiprocessing.Process',
        side_effect=mocked_multiprocessing_process,
        autospec=True)
    def test_emitter_csv_kafka_failed_new_process(self, mock_process):
        metadata = {}
        metadata['namespace'] = 'namespace777'
        retries = 2
        with self.assertRaises(OSError):
            with Emitter(urls=['kafka://1.1.1.1:123/timeouttopic'],
                         emitter_args=metadata,
                         max_emit_retries=retries,
                         kafka_timeout_secs=0.1) as emitter:
                emitter.emit("dummy", {'test': 'bla'}, 'dummy')

    @mock.patch('crawler.emitter.pykafka.KafkaClient',
                side_effect=MockedKafkaClient2, autospec=True)
    @mock.patch('crawler.emitter.kafka_python.KafkaClient',
                side_effect=MockedKafkaClient1, autospec=True)
    def test_emitter_kafka_send(self, MockC1, MockC2):
        (temp_fd, path) = tempfile.mkstemp(prefix='emit.')
        os.close(temp_fd)  # close temporary file descriptor
        emitfile = open(path, 'wb')
        tmp_message = 'a.b.c 1 1\r\n'
        emitfile.write(tmp_message)
        emitfile.write(tmp_message)
        emitfile.close()

        try:
            crawler.emitter.kafka_send('1.1.1.1', path, 'csv', 'topic1')
            crawler.emitter.kafka_send('1.1.1.1', path, 'graphite', 'topic1')
            with self.assertRaises(RandomKafkaException):
                crawler.emitter.kafka_send('1.1.1.1', path, 'csv', 'badtopic')
            with self.assertRaises(RandomKafkaException):
                crawler.emitter.kafka_send(
                    '1.1.1.1', path, 'graphite', 'badtopic')
            with self.assertRaises(crawler.crawler_exceptions.EmitterUnsupportedFormat):
                crawler.emitter.kafka_send('1.1.1.1', path, 'xxx', 'badtopic')
        finally:
            os.remove(path)
        self.assertEqual(MockC1.call_count, 5)
        self.assertEqual(MockC1.call_count, 5)

    @mock.patch('crawler.emitter.MTGraphiteClient',
                side_effect=MockedMTGraphiteClient, autospec=True)
    @mock.patch('crawler.emitter.time.sleep')
    def test_emitter_mtgraphite(self, mock_sleep, MockMTGraphiteClient):
        metadata = {}
        metadata['namespace'] = 'namespace777'
        retries = 2
        with Emitter(urls=['mtgraphite://1.1.1.1:123/topic1'],
                     emitter_args=metadata,
                     max_emit_retries=retries) as emitter:
            emitter.emit("dummy_feature",
                         {'test': 'bla',
                          'test2': 12345,
                          'test3': 12345.0,
                          'test4': 12345.00000},
                         'dummy_feature')
            emitter.emit("dummy_feature",
                         {'test': 'bla',
                          'test2': 12345,
                          'test3': 12345.0,
                          'test4': 12345.00000},
                         'dummy_feature')

        metadata = {}
        metadata['namespace'] = 'namespace777'
        retries = 2
        with Emitter(urls=['mtgraphite://1.1.1.1:123/topic1'],
                     emitter_args=metadata,
                     format='graphite',
                     max_emit_retries=retries) as emitter:
            emitter.emit("dummy_feature",
                         {'test': 'bla',
                          'test2': 12345,
                          'test3': 12345.0,
                          'test4': 12345.00000},
                         'dummy_feature')
            emitter.emit("dummy_feature",
                         {'test': 'bla',
                          'test2': 12345,
                          'test3': 12345.0,
                          'test4': 12345.00000},
                         'dummy_feature')
        """
        The thing with the mtgraphite client is that it's a static long standing
        connection, so if you instantiate lots of Emitter's, the connection
        will be created once; i.e. the client will be instantiated once.
        """
        self.assertEqual(MockMTGraphiteClient.call_count, 1)

    '''
    for 'json' format, the conversion happens for 'http' targets
    at send time. It still uses 'csv' format for temporary storage.
    '''
    @mock.patch('crawler.emitter.requests.post',
                side_effect=mocked_requests_post)
    @mock.patch('crawler.emitter.time.sleep')
    def test_emitter_json_http_simple(self, mock_sleep, mock_post):
        metadata = {}
        metadata['namespace'] = 'namespace777'
        retries = 5
        with Emitter(urls=['http://1.1.1.1/good'],
                     emitter_args=metadata,
                     format='json',
                     max_emit_retries=retries) as emitter:
            emitter.emit("dummy_feature",
                         {'test': 'bla',
                          'test2': 12345,
                          'test3': 12345.0,
                          'test4': 12345.00000},
                         'dummy_feature')
            emitter.emit("dummy_feature",
                         {'test': 'bla',
                          'test2': 12345,
                          'test3': 12345.0,
                          'test4': 12345.00000},
                         'dummy_feature')
        '''
        we expect call_count to be equal to number of
        emit data + 1 (metadata)
        '''
        self.assertEqual(mock_post.call_count, 3)
