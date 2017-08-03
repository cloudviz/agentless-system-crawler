from unittest import TestCase

import mock

from plugins.applications.nginx import nginx_crawler
from plugins.applications.nginx.feature import NginxFeature
from plugins.applications.nginx.nginx_container_crawler \
    import NginxContainerCrawler
from plugins.applications.nginx.nginx_host_crawler \
    import NginxHostCrawler
from utils.crawler_exceptions import CrawlError


# expected format from nginx status page
def mocked_retrieve_status_page(host, port):
    return ('Active connections: 2\n'
            'server accepts handled requests\n'
            '2 2 1\n'
            'Reading: 0 Writing: 1 Waiting: 1'
            )


def mocked_no_status_page(host, port):
    # raise urllib2.HTTPError(1,2,3,4,5)
    raise Exception


def mocked_wrong_status_page(host, port):
    return ('No Acceptable status page format')


def mocked_urllib2_open(request):
    return MockedURLResponse()


class MockedURLResponse(object):

    def read(self):
        return ('Active connections: 2\n'
                'server accepts handled requests\n'
                '2 2 1\n'
                'Reading: 0 Writing: 1 Waiting: 1'
                )


class MockedNginxContainer(object):

    def __init__(
            self,
            container_id,
    ):
        self.image_name = 'nginx-container'

    def get_container_ip(self):
        return '1.2.3.4'

    def get_container_ports(self):
        ports = [80, 443]
        return ports


class MockedNoPortContainer(object):

    def __init__(
            self,
            container_id,
    ):
        self.image_name = 'nginx-container'

    def get_container_ip(self):
        return '1.2.3.4'

    def get_container_ports(self):
        ports = []
        return ports


class MockedNoNameContainer(object):

    def __init__(self, container_id):
        self.image_name = 'dummy'


class NginxCrawlTests(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    @mock.patch('urllib2.urlopen', mocked_urllib2_open)
    def test_ok(self):
        self.assertIsInstance(nginx_crawler.retrieve_metrics(),
                              NginxFeature)

    '''
    @mock.patch('plugins.applications.nginx.'
                'nginx_crawler.retrieve_status_page',
                mocked_retrieve_status_page)
    def test_successful_crawling(self):
        self.assertIsInstance(nginx_crawler.retrieve_metrics(),
                              NginxFeature)
    '''
    @mock.patch('plugins.applications.nginx.'
                'nginx_crawler.retrieve_status_page',
                mocked_no_status_page)
    def test_hundle_ioerror(self):
        with self.assertRaises(CrawlError):
            nginx_crawler.retrieve_metrics()

    @mock.patch('plugins.applications.nginx.'
                'nginx_crawler.retrieve_status_page',
                mocked_wrong_status_page)
    def test_hundle_parseerror(self):
        with self.assertRaises(CrawlError):
            nginx_crawler.retrieve_metrics()


class NginxHostTest(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_get_feature(self):
        c = NginxHostCrawler()
        self.assertEqual(c.get_feature(), 'nginx')

    @mock.patch('plugins.applications.nginx.'
                'nginx_crawler.retrieve_status_page',
                mocked_retrieve_status_page)
    def test_get_metrics(self):
        c = NginxHostCrawler()
        emitted = c.crawl()[0]
        self.assertEqual(emitted[0], 'nginx')
        self.assertIsInstance(emitted[1], NginxFeature)
        self.assertEqual(emitted[2], 'application')


class NginxContainerTest(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_get_feature(self):
        c = NginxContainerCrawler()
        self.assertEqual(c.get_feature(), 'nginx')

    @mock.patch('plugins.applications.nginx.'
                'nginx_crawler.retrieve_status_page',
                mocked_retrieve_status_page)
    @mock.patch('dockercontainer.DockerContainer',
                MockedNginxContainer)
    def test_get_metrics(self):
        c = NginxContainerCrawler()
        emitted = c.crawl()[0]
        self.assertEqual(emitted[0], 'nginx')
        self.assertIsInstance(emitted[1], NginxFeature)
        self.assertEqual(emitted[2], 'application')

    @mock.patch('dockercontainer.DockerContainer',
                MockedNoPortContainer)
    def test_no_available_port(self):
        c = NginxContainerCrawler()
        with self.assertRaises(CrawlError):
            c.crawl("mockcontainer")

    @mock.patch('dockercontainer.DockerContainer',
                MockedNoNameContainer)
    def test_none_nginx_container(self):
        c = NginxContainerCrawler()
        with self.assertRaises(CrawlError):
            c.crawl("mockcontainer")

    @mock.patch('plugins.applications.nginx.'
                'nginx_crawler.retrieve_status_page',
                mocked_no_status_page)
    @mock.patch('dockercontainer.DockerContainer',
                MockedNginxContainer)
    def test_no_accessible_endpoint(self):
        c = NginxContainerCrawler()
        with self.assertRaises(CrawlError):
            c.crawl("mockcontainer")
