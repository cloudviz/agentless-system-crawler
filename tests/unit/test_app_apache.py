from unittest import TestCase

import mock

from plugins.applications.apache import apache_crawler
from plugins.applications.apache.feature import ApacheFeature
from plugins.applications.apache.apache_container_crawler \
    import ApacheContainerCrawler
from plugins.applications.apache.apache_host_crawler \
    import ApacheHostCrawler
from utils.crawler_exceptions import CrawlError


# expected format from apache status page

def mocked_wrong_status_page(host, port):
    return ('No Acceptable status page format')


def mocked_urllib2_open(request):
    return MockedURLResponse()


def mocked_urllib2_open_with_zero(request):
    return MockedURLResponseWithZero()


def mocked_no_status_page(host, port):
    raise Exception


def mocked_retrieve_status_page(host, port):
    return ('Total Accesses: 172\n'
            'Total kBytes: 1182\n'
            'CPULoad: 2.34827\n'
            'Uptime: 1183\n'
            'ReqPerSec: .145393\n'
            'BytesPerSec: 1023.13\n'
            'BytesPerReq: 7037.02\n'
            'BusyWorkers: 2\n'
            'IdleWorkers: 9\n'
            'Scoreboard: __R_W______......G..C...'
            'DSKLI...............................'
            '...................................................'
            )


class MockedURLResponse(object):

    def read(self):
        return ('Total Accesses: 172\n'
                'Total kBytes: 1182\n'
                'CPULoad: 2.34827\n'
                'Uptime: 1183\n'
                'ReqPerSec: .145393\n'
                'BytesPerSec: 1023.13\n'
                'BytesPerReq: 7037.02\n'
                'BusyWorkers: 2\n'
                'IdleWorkers: 9\n'
                'Scoreboard: __R_W______......G..'
                'C...DSKLI........................'
                '..........................................................'
                )


class MockedURLResponseWithZero(object):

    def read(self):
        return ('Total Accesses: 172\n'
                'Total kBytes: 1182\n'
                'CPULoad: 2.34827\n'
                'ReqPerSec: .145393\n'
                'BytesPerSec: 1023.13\n'
                'BytesPerReq: 7037.02\n'
                'BusyWorkers: 2\n'
                'IdleWorkers: 9\n'
                'Scoreboard: __R_W______......G..C...'
                'DSKLI................................'
                '..................................................'
                )


class MockedApacheContainer(object):

    def __init__(
            self,
            container_id,
    ):
        self.image_name = 'httpd-container'

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
        self.image_name = 'httpd-container'

    def get_container_ip(self):
        return '1.2.3.4'

    def get_container_ports(self):
        ports = []
        return ports


class MockedNoNameContainer(object):

    def __init__(self, container_id):
        self.image_name = 'dummy'


class ApacheCrawlTests(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    @mock.patch('urllib2.urlopen', mocked_urllib2_open_with_zero)
    def test_ok_with_zero(self):
        status = apache_crawler.retrieve_metrics()
        assert status == ApacheFeature(
            BusyWorkers='2',
            IdleWorkers='9',
            waiting_for_connection='9',
            starting_up='1',
            reading_request='1',
            sending_reply='1',
            keepalive_read='1',
            dns_lookup='1',
            closing_connection='1',
            logging='1',
            graceful_finishing='1',
            idle_worker_cleanup='1',
            BytesPerSec='1023.13',
            BytesPerReq='7037.02',
            ReqPerSec='.145393',
            Uptime='0',
            Total_kBytes='1182',
            Total_Accesses='172')

    @mock.patch('urllib2.urlopen', mocked_urllib2_open)
    def test_ok(self):
        status = apache_crawler.retrieve_metrics()
        assert status == ApacheFeature(
            BusyWorkers='2',
            IdleWorkers='9',
            waiting_for_connection='9',
            starting_up='1',
            reading_request='1',
            sending_reply='1',
            keepalive_read='1',
            dns_lookup='1',
            closing_connection='1',
            logging='1',
            graceful_finishing='1',
            idle_worker_cleanup='1',
            BytesPerSec='1023.13',
            BytesPerReq='7037.02',
            ReqPerSec='.145393',
            Uptime='1183',
            Total_kBytes='1182',
            Total_Accesses='172')

    @mock.patch('plugins.applications.apache.'
                'apache_crawler.retrieve_status_page',
                mocked_no_status_page)
    def test_hundle_ioerror(self):
        with self.assertRaises(CrawlError):
            apache_crawler.retrieve_metrics()

    @mock.patch('plugins.applications.apache.'
                'apache_crawler.retrieve_status_page',
                mocked_wrong_status_page)
    def test_hundle_parseerror(self):
        with self.assertRaises(CrawlError):
            apache_crawler.retrieve_metrics()


class ApacheHostTest(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_get_feature(self):
        c = ApacheHostCrawler()
        self.assertEqual(c.get_feature(), 'apache')

    @mock.patch('plugins.applications.apache.'
                'apache_crawler.retrieve_status_page',
                mocked_retrieve_status_page)
    def test_get_metrics(self):
        c = ApacheHostCrawler()
        emitted = c.crawl()[0]
        self.assertEqual(emitted[0], 'apache')
        self.assertIsInstance(emitted[1], ApacheFeature)
        self.assertEqual(emitted[2], 'application')


class ApacheContainerTest(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_get_feature(self):
        c = ApacheContainerCrawler()
        self.assertEqual(c.get_feature(), 'apache')

    @mock.patch('plugins.applications.apache.'
                'apache_crawler.retrieve_status_page',
                mocked_retrieve_status_page)
    @mock.patch('dockercontainer.DockerContainer',
                MockedApacheContainer)
    def test_get_metrics(self):
        c = ApacheContainerCrawler()
        emitted = c.crawl()[0]
        self.assertEqual(emitted[0], 'apache')
        self.assertIsInstance(emitted[1], ApacheFeature)
        self.assertEqual(emitted[2], 'application')

    @mock.patch('dockercontainer.DockerContainer',
                MockedNoPortContainer)
    def test_no_available_port(self):
        c = ApacheContainerCrawler()
        with self.assertRaises(CrawlError):
            c.crawl("mockcontainer")

    @mock.patch('dockercontainer.DockerContainer',
                MockedNoNameContainer)
    def test_none_apache_container(self):
        c = ApacheContainerCrawler()
        with self.assertRaises(CrawlError):
            c.crawl("mockcontainer")

    @mock.patch('plugins.applications.apache.'
                'apache_crawler.retrieve_status_page',
                mocked_no_status_page)
    @mock.patch('dockercontainer.DockerContainer',
                MockedApacheContainer)
    def test_no_accessible_endpoint(self):
        c = ApacheContainerCrawler()
        with self.assertRaises(CrawlError):
            c.crawl("mockcontainer")
