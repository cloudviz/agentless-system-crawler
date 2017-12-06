from unittest import TestCase
import mock
from plugins.applications.nginx import nginx_crawler
from plugins.applications.nginx.feature import NginxFeature
from plugins.applications.nginx.nginx_container_crawler \
    import NginxContainerCrawler
from plugins.applications.nginx.nginx_host_crawler \
    import NginxHostCrawler
from utils.crawler_exceptions import CrawlError
from requests.exceptions import ConnectionError


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


class MockedNginxContainer1(object):

    def __init__(self, container_id):
        ports = "[ {\"containerPort\" : \"80\"} ]"
        self.inspect = {"State": {"Pid": 1234}, "Config": {"Labels":
                                                           {"annotation.io.kubernetes.container.ports": ports}}}


class MockedNginxContainer2(object):

    def __init__(self, container_id):
        self.inspect = {"State": {"Pid": 1234},
                        "Config": {"Labels": {"dummy": "dummy"}}}

    def get_container_ports(self):
        ports = ["80"]
        return ports


class MockedNginxContainer3(object):

    def __init__(self, container_id):
        self.inspect = {"State": {"Pid": 1234},
                        "Config": {"Labels": {"dummy": "dummy"}}}

    def get_container_ports(self):
        ports = ["1234"]
        return ports


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
                MockedNginxContainer1)
    @mock.patch(("plugins.applications.nginx.nginx_container_crawler."
                 "run_as_another_namespace"),
                return_value=['127.0.0.1', '1.2.3.4'])
    def test_nginx_container_forkube(self, *args):
        c = NginxContainerCrawler()
        emitted = c.crawl()[0]
        self.assertEqual(emitted[0], 'nginx')
        self.assertIsInstance(emitted[1], NginxFeature)
        self.assertEqual(emitted[2], 'application')

    @mock.patch('plugins.applications.nginx.'
                'nginx_crawler.retrieve_status_page',
                mocked_retrieve_status_page)
    @mock.patch('dockercontainer.DockerContainer',
                MockedNginxContainer2)
    @mock.patch(("plugins.applications.nginx.nginx_container_crawler."
                 "run_as_another_namespace"),
                return_value=['127.0.0.1', '1.2.3.4'])
    def test_nginx_container_fordocker(self, *args):
        c = NginxContainerCrawler()
        emitted = c.crawl()[0]
        self.assertEqual(emitted[0], 'nginx')
        self.assertIsInstance(emitted[1], NginxFeature)
        self.assertEqual(emitted[2], 'application')

    @mock.patch('dockercontainer.DockerContainer',
                MockedNginxContainer3)
    def test_nginx_container_noport(self, *args):
        c = NginxContainerCrawler()
        c.crawl(1234)
        pass

    @mock.patch('plugins.applications.nginx.'
                'nginx_crawler.retrieve_status_page',
                mocked_no_status_page)
    @mock.patch('dockercontainer.DockerContainer',
                MockedNginxContainer2)
    @mock.patch(("plugins.applications.nginx.nginx_container_crawler."
                 "run_as_another_namespace"),
                return_value=['127.0.0.1', '1.2.3.4'])
    def test_no_accessible_endpoint(self, *arg):
        c = NginxContainerCrawler()
        with self.assertRaises(ConnectionError):
            c.crawl("mockcontainer")
