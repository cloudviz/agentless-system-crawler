import mock
import unittest
import os

from crawler.crawlutils import (snapshot_generic,
                                snapshot_container,
                                snapshot_mesos)
from crawler.crawlmodes import Modes


class MockedDockerContainer:
    def __init__(self):
        self.namespace = 'namespace'
        self.short_id = 'short_id'
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

class MockedEmitter:
    def __init__(self, urls=None, emitter_args=None, format='csv'):
        self.emitter_args = emitter_args
        if emitter_args['system_type'] == 'container':
            assert urls == ['stdout://', 'file:///tmp/frame.short_id.123',
                            'kafka://ip:123/topic']
        else:
            assert urls == ['stdout://', 'file:///tmp/frame.123',
                            'kafka://ip:123/topic']
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
                         features='os',
                         urls=['stdout://', 'file:///tmp/frame',
                               'kafka://ip:123/topic'],
                         ignore_exceptions=False)
        # MockedEmitter is doing all the checks


    @mock.patch('crawler.crawlutils.features_crawler.FeaturesCrawler',
                side_effect=MockedFeaturesCrawlerFailure, autospec=True)
    @mock.patch('crawler.crawlutils.Emitter',
                side_effect=MockedEmitter, autospec=True)
    def test_snapshot_generic_invm_failure(self, *args):
        with self.assertRaises(OSError):
            snapshot_generic(crawlmode=Modes.INVM,
                             snapshot_num=123,
                             features='os',
                             urls=['stdout://', 'file:///tmp/frame',
                                   'kafka://ip:123/topic'],
                             ignore_exceptions=False)

    @mock.patch('crawler.crawlutils.features_crawler.FeaturesCrawler',
                side_effect=MockedFeaturesCrawler, autospec=True)
    @mock.patch('crawler.crawlutils.Emitter',
                side_effect=MockedEmitter, autospec=True)
    def test_snapshot_generic_outcontainer(self, *args):
        snapshot_container(snapshot_num=123,
                           container=MockedDockerContainer(),
                           features='os',
                           urls=['stdout://', 'file:///tmp/frame',
                                 'kafka://ip:123/topic'],
                           ignore_exceptions=False)
        # MockedEmitter is doing all the checks


    @mock.patch('crawler.crawlutils.features_crawler.FeaturesCrawler',
                side_effect=MockedFeaturesCrawlerFailure, autospec=True)
    @mock.patch('crawler.crawlutils.Emitter',
                side_effect=MockedEmitter, autospec=True)
    def test_snapshot_generic_outcontainer_failure(self, *args):
        with self.assertRaises(OSError):
            snapshot_container(snapshot_num=123,
                               container=MockedDockerContainer(),
                               features='os',
                               urls=['stdout://', 'file:///tmp/frame',
                                     'kafka://ip:123/topic'],
                               ignore_exceptions=False)

    @mock.patch('crawler.crawlutils.snapshot_crawler_mesos_frame',
                side_effect=lambda options : {'mesos'})
    @mock.patch('crawler.crawlutils.Emitter',
                side_effect=MockedEmitter, autospec=True)
    def test_snapshot_mesos(self, *args):
        snapshot_mesos(snapshot_num=123,
                       features='frame',
                       urls=['stdout://', 'file:///tmp/frame',
                             'kafka://ip:123/topic'],
                       ignore_exceptions=False)
        # MockedEmitter is doing all the checks


    @mock.patch('crawler.crawlutils.snapshot_crawler_mesos_frame',
                side_effect=throw_os_error)
    @mock.patch('crawler.crawlutils.Emitter',
                side_effect=MockedEmitter, autospec=True)
    def test_snapshot_mesos(self, *args):
        with self.assertRaises(OSError):
            snapshot_mesos(snapshot_num=123,
                           features='frame',
                           urls=['stdout://', 'file:///tmp/frame',
                                 'kafka://ip:123/topic'],
                           ignore_exceptions=False)
