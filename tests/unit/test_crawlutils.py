import mock
import unittest

# for OUTVM psvmi
from mock import Mock
import sys
sys.modules['psvmi'] = Mock()

from crawler.crawlutils import (snapshot_generic,
                                snapshot_container,
                                snapshot_mesos,
                                snapshot)
from crawler.crawlmodes import Modes


class MockedDockerContainer:

    def __init__(self, short_id='short_id', pid=777):
        self.namespace = 'namespace'
        self.pid = pid
        self.short_id = short_id
        self.long_id = 'long_id'
        self.name = 'name'
        self.image = 'image'
        self.owner_namespace = 'owner_namespace'
        self.docker_image_long_name = 'image_long_name'
        self.docker_image_short_name = 'image_short_name'
        self.docker_image_tag = 'image_tag'
        self.docker_image_registry = 'image_registry'

    def is_docker_container(self):
        return True

    def link_logfiles(self, options):
        pass

    def unlink_logfiles(self, options):
        pass

    def __eq__(self, other):
        return self.pid == other.pid


class MockedEmitter:

    def __init__(self, urls=None, emitter_args=None, format='csv'):
        self.emitter_args = emitter_args
        if emitter_args['system_type'] == 'container':
            assert (urls == ['stdout://', 'file:///tmp/frame.short_id.123',
                             'kafka://ip:123/topic'] or

                    urls == ['stdout://', 'file:///tmp/frame.short_id.124',
                             'kafka://ip:123/topic'])
        else:
            assert (urls == ['stdout://', 'file:///tmp/frame.123',
                             'kafka://ip:123/topic'] or
                    urls == ['stdout://', 'file:///tmp/frame.124',
                             'kafka://ip:123/topic'])
        self.args = None

    def emit(self, *args):
        self.args = args

    def __enter__(self, *args, **kwargs):
        return self

    def __exit__(self, typ, exc, trc):
        if exc:
            raise exc
        if self.emitter_args['system_type'] != 'mesos':
            assert self.args == ('linux', {'os': 'some_os'}, 'os')


class MockedFeaturesCrawler:

    def __init__(self, *args, **kwargs):
        self.funcdict = {
            'os': self.crawl_os
        }

    def crawl_os(self, *args, **kwargs):
        yield ('linux', {'os': 'some_os'})


class MockedFeaturesCrawlerFailure:

    def __init__(self, *args, **kwargs):
        self.funcdict = {
            'os': self.crawl_os
        }

    def crawl_os(self, *args, **kwargs):
        raise OSError('some exception')


def throw_os_error(*args, **kwargs):
    raise OSError()


class ContainerTests(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    @mock.patch('crawler.crawlutils.features_crawler.FeaturesCrawler',
                side_effect=MockedFeaturesCrawler, autospec=True)
    @mock.patch('crawler.crawlutils.Emitter',
                side_effect=MockedEmitter, autospec=True)
    def test_snapshot_generic_invm(self, *args):
        snapshot_generic(crawlmode=Modes.INVM,
                         snapshot_num=123,
                         features=['os'],
                         urls=['stdout://', 'file:///tmp/frame',
                               'kafka://ip:123/topic'],
                         ignore_exceptions=False)
        # MockedEmitter is doing all the checks
        assert args[0].call_count == 1
        assert args[1].call_count == 1

    @mock.patch('crawler.crawlutils.features_crawler.FeaturesCrawler',
                side_effect=MockedFeaturesCrawlerFailure, autospec=True)
    @mock.patch('crawler.crawlutils.Emitter',
                side_effect=MockedEmitter, autospec=True)
    def test_snapshot_generic_invm_failure(self, *args):
        with self.assertRaises(OSError):
            snapshot_generic(crawlmode=Modes.INVM,
                             snapshot_num=123,
                             features=['os'],
                             urls=['stdout://', 'file:///tmp/frame',
                                   'kafka://ip:123/topic'],
                             ignore_exceptions=False)
        assert args[0].call_count == 1
        assert args[1].call_count == 1

    @mock.patch('crawler.crawlutils.features_crawler.FeaturesCrawler',
                side_effect=MockedFeaturesCrawler, autospec=True)
    @mock.patch('crawler.crawlutils.Emitter',
                side_effect=MockedEmitter, autospec=True)
    @mock.patch(
        ("crawler.crawlutils.plugins_manager."
            "get_container_crawl_plugins"),
        side_effect=lambda features: [])
    def test_snapshot_generic_outcontainer(self, *args):
        snapshot_container(snapshot_num=123,
                           container=MockedDockerContainer(),
                           features=['os'],
                           urls=['stdout://', 'file:///tmp/frame',
                                 'kafka://ip:123/topic'],
                           ignore_exceptions=False)
        # MockedEmitter is doing all the checks
        assert args[0].call_count == 1
        assert args[1].call_count == 1

    @mock.patch('crawler.crawlutils.features_crawler.FeaturesCrawler',
                side_effect=MockedFeaturesCrawlerFailure, autospec=True)
    @mock.patch('crawler.crawlutils.Emitter',
                side_effect=MockedEmitter, autospec=True)
    @mock.patch(
        'crawler.crawlutils.plugins_manager.get_container_crawl_plugins',
        side_effect=lambda features: [])
    def test_snapshot_generic_outcontainer_failure(self, *args):
        with self.assertRaises(OSError):
            snapshot_container(snapshot_num=123,
                               container=MockedDockerContainer(),
                               features=['os'],
                               urls=['stdout://', 'file:///tmp/frame',
                                     'kafka://ip:123/topic'],
                               ignore_exceptions=False)
        assert args[0].call_count == 1
        assert args[1].call_count == 1

    @mock.patch('crawler.crawlutils.snapshot_crawler_mesos_frame',
                side_effect=lambda options: {'mesos'})
    @mock.patch('crawler.crawlutils.Emitter',
                side_effect=MockedEmitter, autospec=True)
    def test_snapshot_mesos(self, *args):
        snapshot_mesos(snapshot_num=123,
                       features=['frame'],
                       urls=['stdout://', 'file:///tmp/frame',
                             'kafka://ip:123/topic'],
                       ignore_exceptions=False)
        # MockedEmitter is doing all the checks
        assert args[0].call_count == 1
        assert args[1].call_count == 1

    @mock.patch('crawler.crawlutils.snapshot_crawler_mesos_frame',
                side_effect=throw_os_error)
    @mock.patch('crawler.crawlutils.Emitter',
                side_effect=MockedEmitter, autospec=True)
    def test_snapshot_mesos(self, *args):
        with self.assertRaises(OSError):
            snapshot_mesos(snapshot_num=123,
                           features=['frame'],
                           urls=['stdout://', 'file:///tmp/frame',
                                 'kafka://ip:123/topic'],
                           ignore_exceptions=False)
        assert args[0].call_count == 1
        assert args[1].call_count == 1

    @mock.patch('crawler.crawlutils.time.sleep')
    @mock.patch('crawler.crawlutils.features_crawler.FeaturesCrawler',
                side_effect=MockedFeaturesCrawler, autospec=True)
    @mock.patch('crawler.crawlutils.Emitter',
                side_effect=MockedEmitter, autospec=True)
    def test_snapshot_invm_two_iters(self, *args):
        snapshot(crawlmode=Modes.INVM,
                 first_snapshot_num=123,
                 features=['os'],
                 frequency=1,
                 max_snapshots=124,
                 urls=['stdout://', 'file:///tmp/frame',
                       'kafka://ip:123/topic'])
        # MockedEmitter is doing all the checks
        assert args[0].call_count == 2
        assert args[1].call_count == 2

    @mock.patch('crawler.crawlutils.time.sleep')
    @mock.patch('crawler.crawlutils.features_crawler.FeaturesCrawler',
                side_effect=MockedFeaturesCrawler, autospec=True)
    @mock.patch('crawler.crawlutils.Emitter',
                side_effect=MockedEmitter, autospec=True)
    def test_snapshot_invm_two_iters_freq_zero(self, *args):
        snapshot(crawlmode=Modes.INVM,
                 first_snapshot_num=123,
                 features=['os'],
                 frequency=0,
                 max_snapshots=124,
                 urls=['stdout://', 'file:///tmp/frame',
                       'kafka://ip:123/topic'])
        # MockedEmitter is doing all the checks
        assert args[0].call_count == 2
        assert args[1].call_count == 2

    @mock.patch('crawler.crawlutils.get_filtered_list_of_containers',
                side_effect=lambda environment, host_namespace, user_list, partition_strategy:
                [MockedDockerContainer(short_id='short_id', pid=101),
                 MockedDockerContainer(short_id='short_id', pid=102),
                 MockedDockerContainer(short_id='short_id', pid=103)])
    @mock.patch('crawler.crawlutils.features_crawler.FeaturesCrawler',
                side_effect=MockedFeaturesCrawler, autospec=True)
    @mock.patch('crawler.crawlutils.Emitter',
                side_effect=MockedEmitter, autospec=True)
    def test_snapshot_outcontainer(self, *args):
        snapshot(crawlmode=Modes.OUTCONTAINER,
                 first_snapshot_num=123,
                 features=['os'],
                 urls=['stdout://', 'file:///tmp/frame',
                       'kafka://ip:123/topic'])
        # MockedEmitter is doing all the checks
        assert args[0].call_count == 3
        assert args[1].call_count == 3

    @mock.patch('crawler.crawlutils.time.sleep')
    @mock.patch('crawler.crawlutils.get_filtered_list_of_containers',
                side_effect=lambda environment, host_namespace, user_list, partition_strategy:
                [MockedDockerContainer(short_id='short_id', pid=101),
                 MockedDockerContainer(short_id='short_id', pid=102),
                 MockedDockerContainer(short_id='short_id', pid=103)])
    @mock.patch('crawler.crawlutils.features_crawler.FeaturesCrawler',
                side_effect=MockedFeaturesCrawler, autospec=True)
    @mock.patch('crawler.crawlutils.Emitter',
                side_effect=MockedEmitter, autospec=True)
    def test_snapshot_outcontainer_two_iters(self, *args):
        snapshot(crawlmode=Modes.OUTCONTAINER,
                 first_snapshot_num=123,
                 features=['os'],
                 frequency=1,
                 max_snapshots=124,
                 urls=['stdout://', 'file:///tmp/frame',
                       'kafka://ip:123/topic'])
        # MockedEmitter is doing all the checks
        assert args[0].call_count == 6
        assert args[1].call_count == 6

    @mock.patch.object(MockedDockerContainer, 'link_logfiles')
    @mock.patch.object(MockedDockerContainer, 'unlink_logfiles')
    @mock.patch('crawler.crawlutils.time.sleep')
    @mock.patch('crawler.crawlutils.get_filtered_list_of_containers',
                side_effect=lambda environment, host_namespace, user_list, partition_strategy:
                [MockedDockerContainer(short_id='short_id', pid=101),
                 MockedDockerContainer(short_id='short_id', pid=102),
                 MockedDockerContainer(short_id='short_id', pid=103)])
    @mock.patch('crawler.crawlutils.features_crawler.FeaturesCrawler',
                side_effect=MockedFeaturesCrawler, autospec=True)
    @mock.patch('crawler.crawlutils.Emitter',
                side_effect=MockedEmitter, autospec=True)
    def test_snapshot_outcontainer_two_iters_with_linking(
            self,
            mock_emitter,
            mock_crawler,
            mock_get_list,
            mock_sleep,
            mock_unlink,
            mock_link):
        options = {'link_container_log_files': True}
        snapshot(crawlmode=Modes.OUTCONTAINER,
                 first_snapshot_num=123,
                 features=['os'],
                 frequency=1,
                 max_snapshots=124,
                 urls=['stdout://', 'file:///tmp/frame',
                       'kafka://ip:123/topic'],
                 options=options)
        # MockedEmitter is doing all the checks
        assert mock_emitter.call_count == 6
        assert mock_crawler.call_count == 6
        assert mock_link.call_count == 6
        # the returned containers are always the same, so no container
        # is deleted
        assert mock_unlink.call_count == 0
