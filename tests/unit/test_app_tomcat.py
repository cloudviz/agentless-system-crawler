from unittest import TestCase

import mock

from plugins.applications.tomcat import tomcat_crawler
from plugins.applications.tomcat import feature
from plugins.applications.tomcat.tomcat_container_crawler \
    import TomcatContainerCrawler
from plugins.applications.tomcat.tomcat_host_crawler \
    import TomcatHostCrawler
from utils.crawler_exceptions import CrawlError


def mocked_urllib2_open(request):
    return MockedURLResponse()


def mocked_retrieve_status_page(host, port, user, password):
    return server_status_value()


def server_status_value():
    return ('<?xml version="1.0" encoding="utf-8"?>'
            '<?xml-stylesheet type="text/xsl" href="/manager/xform.xsl" ?>'
            '<status><jvm><memory free=\'3846720\''
            '  total=\'62390272\' max=\'922746880\'/>'
            '<memorypool name=\'PS Eden Space\' type=\'Heap memory\''
            ' usageInit=\'16252928\' usageCommitted=\'16252928\''
            ' usageMax=\'340787200\' usageUsed=\'8570016\'/>'
            '<memorypool name=\'PS Survivor Space\' type=\'Heap memory\''
            ' usageInit=\'2621440\' usageCommitted=\'2621440\''
            ' usageMax=\'2621440\' usageUsed=\'2621440\'/>'
            '<memorypool name=\'Code Cache\' type=\'Non-heap memory\''
            ' usageInit=\'2555904\' usageCommitted=\'6225920\''
            ' usageMax=\'251658240\' usageUsed=\'6211200\'/>'
            '<memorypool name=\'Compressed Class Space\''
            ' type=\'Non-heap memory\' usageInit=\'0\''
            ' usageCommitted=\'2097152\' usageMax=\'1073741824\''
            ' usageUsed=\'1959616\'/>'
            '<memorypool name=\'Metaspace\' type=\'Non-heap memory\''
            ' usageInit=\'0\' usageCommitted=\'18874368\''
            ' usageMax=\'-1\' usageUsed=\'18211520\'/>'
            '</jvm>'
            '<connector name="ajp-nio-8009">'
            '<threadInfo  maxThreads="200" currentThreadCount="0"'
            ' currentThreadsBusy="0" />'
            '<requestInfo  maxTime="0" processingTime="0" requestCount="0"'
            ' errorCount="0" bytesReceived="0" bytesSent="0" />'
            '<workers></workers>'
            '</connector>'
            '<connector name="http-nio-8080"><threadInfo  maxThreads="200"'
            ' currentThreadCount="2" currentThreadsBusy="1" />'
            '<requestInfo  maxTime="60" processingTime="60"'
            ' requestCount="1" errorCount="1"'
            ' bytesReceived="0" bytesSent="2473" />'
            '<workers><worker  stage="S" requestProcessingTime="52"'
            ' requestBytesSent="0" requestBytesReceived="0"'
            ' remoteAddr="0:0:0:0:0:0:0:1" virtualHost="localhost"'
            ' method="GET" currentUri="/manager/status"'
            ' currentQueryString="XML=true" protocol="HTTP/1.1" />'
            '</workers>'
            '</connector>'
            '</status>'
            )


class MockedURLResponse(object):
    def read(self):
        return server_status_value()


class MockedTomcatContainer(object):

    def __init__(
            self,
            container_id,
    ):
        self.image_name = 'tomcat'

    def get_container_ip(self):
        return '1.2.3.4'

    def get_container_ports(self):
        ports = [8080, 443]
        return ports


class MockedNoPortContainer(object):

    def __init__(
            self,
            container_id,
    ):
        self.image_name = 'tomcat'

    def get_container_ip(self):
        return '1.2.3.4'

    def get_container_ports(self):
        ports = []
        return ports


class MockedNoNameContainer(object):

    def __init__(self, container_id):
        self.image_name = 'dummy'


class TomcatCrawlTests(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_hundle_ioerror(self):
        with self.assertRaises(CrawlError):
            tomcat_crawler.retrieve_status_page("localhost",
                                                "1234", "test", "test")

    @mock.patch('urllib2.urlopen', mocked_urllib2_open)
    def test_ok(self):
        status = list(tomcat_crawler.retrieve_metrics())
        assert status == [('tomcat_jvm',
                           feature.TomcatJVMFeature(
                               free='3846720',
                               total='62390272',
                               max='922746880'),
                           'application'),
                          ('tomcat_memory',
                           feature.TomcatMemoryFeature(
                               name='PS Eden Space',
                               type='Heap memory',
                               initial='16252928',
                               committed='16252928',
                               maximum='340787200',
                               used='8570016'),
                           'application'),
                          ('tomcat_memory',
                           feature.TomcatMemoryFeature(
                               name='PS Survivor Space',
                               type='Heap memory',
                               initial='2621440',
                               committed='2621440',
                               maximum='2621440',
                               used='2621440'),
                           'application'),
                          ('tomcat_memory',
                           feature.TomcatMemoryFeature(
                               name='Code Cache',
                               type='Non-heap memory',
                               initial='2555904',
                               committed='6225920',
                               maximum='251658240',
                               used='6211200'),
                           'application'),
                          ('tomcat_memory',
                           feature.TomcatMemoryFeature(
                               name='Compressed Class Space',
                               type='Non-heap memory',
                               initial='0',
                               committed='2097152',
                               maximum='1073741824',
                               used='1959616'),
                           'application'),
                          ('tomcat_memory',
                           feature.TomcatMemoryFeature(
                               name='Metaspace',
                               type='Non-heap memory',
                               initial='0',
                               committed='18874368',
                               maximum='-1',
                               used='18211520'),
                           'application'),
                          ('tomcat_connector',
                           feature.TomcatConnectorFeature(
                               connector='ajp-nio-8009',
                               maxThread='200',
                               currentThread='0',
                               currentThreadBusy='0',
                               requestMaxTime='0',
                               processingTime='0',
                               requestCount='0',
                               errorCount='0',
                               byteReceived='0',
                               byteSent='0'),
                           'application'),
                          ('tomcat_connector',
                           feature.TomcatConnectorFeature(
                               connector='http-nio-8080',
                               maxThread='200',
                               currentThread='2',
                               currentThreadBusy='1',
                               requestMaxTime='60',
                               processingTime='60',
                               requestCount='1',
                               errorCount='1',
                               byteReceived='0',
                               byteSent='2473'),
                           'application'),
                          ('tomcat_worker',
                           feature.TomcatWorkerFeature(
                               connector='http-nio-8080',
                               stage='S',
                               time='52',
                               byteSent='0',
                               byteReceived='0',
                               client='0:0:0:0:0:0:0:1',
                               vhost='localhost',
                               request='/manager/status'),
                           'application')]


class TomcatHostTest(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_get_feature(self):
        c = TomcatHostCrawler()
        self.assertEqual(c.get_feature(), 'tomcat')

    @mock.patch('plugins.applications.tomcat.'
                'tomcat_crawler.retrieve_status_page',
                mocked_retrieve_status_page)
    def test_get_metrics(self):
        c = TomcatHostCrawler()
        options = {"password": "password", "user": "tomcat"}
        emitted = list(c.crawl(**options))
        self.assertEqual(emitted[0][0], 'tomcat_jvm')
        self.assertEqual(emitted[0][2], 'application')


class TomcatContainerTest(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_get_feature(self):
        c = TomcatContainerCrawler()
        self.assertEqual(c.get_feature(), 'tomcat')

    @mock.patch('plugins.applications.tomcat.'
                'tomcat_crawler.retrieve_status_page',
                mocked_retrieve_status_page)
    @mock.patch('dockercontainer.DockerContainer',
                MockedTomcatContainer)
    def test_get_metrics(self):
        c = TomcatContainerCrawler()
        options = {"password": "password", "user": "tomcat"}
        emitted = list(c.crawl(**options))
        self.assertEqual(emitted[0][0], 'tomcat_jvm')
        self.assertEqual(emitted[0][2], 'application')

    @mock.patch('dockercontainer.DockerContainer',
                MockedNoPortContainer)
    def test_no_available_port(self):
        c = TomcatContainerCrawler()
        with self.assertRaises(CrawlError):
            c.crawl("mockcontainer")

    @mock.patch('dockercontainer.DockerContainer',
                MockedNoNameContainer)
    def test_none_tomcat_container(self):
        c = TomcatContainerCrawler()
        with self.assertRaises(CrawlError):
            c.crawl("mockcontainer")
