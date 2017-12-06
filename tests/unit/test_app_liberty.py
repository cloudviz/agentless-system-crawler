from unittest import TestCase
import mock
from plugins.applications.liberty import liberty_crawler
from plugins.applications.liberty import feature
from plugins.applications.liberty.liberty_container_crawler \
    import LibertyContainerCrawler
from plugins.applications.liberty.liberty_host_crawler \
    import LibertyHostCrawler
from utils.crawler_exceptions import CrawlError
from requests.exceptions import ConnectionError


def mocked_urllib2_open(request):
    return MockedURLResponse()


def mock_status_value(user, password, url):
    raise CrawlError


class MockedLibertyContainer1(object):

    def __init__(self, container_id):
        ports = "[ {\"containerPort\" : \"9443\"} ]"
        self.inspect = {"State": {"Pid": 1234}, "Config": {"Labels":
                                                           {"annotation.io.kubernetes.container.ports": ports}}}


class MockedLibertyContainer2(object):

    def __init__(self, container_id):
        self.inspect = {"State": {"Pid": 1234},
                        "Config": {"Labels": {"dummy": "dummy"}}}

    def get_container_ports(self):
        ports = ["9443"]
        return ports


class MockedLibertyContainer3(object):

    def __init__(self, container_id):
        self.inspect = {"State": {"Pid": 1234},
                        "Config": {"Labels": {"dummy": "dummy"}}}

    def get_container_ports(self):
        ports = ["1234"]
        return ports


class MockedURLResponse(object):
    def read(self):
        return open('tests/unit/liberty_response_time_details_mocked',
                    'r').read()


def server_status_value(user, password, url):
    url_list = url.lstrip('/').split("/")
    url_list = filter(lambda a: a != '', url_list)
    tmp_word = url_list[len(url_list)-1]
    last_word = tmp_word.split('%3D')
    last_word = last_word[len(last_word)-1]

    file_value = {
        "mbeans": 'tests/unit/liberty_mbeans',
        "ServletStats": 'tests/unit/liberty_servlet_stats',
        "ResponseTimeDetails": 'tests/unit/liberty_response_time_details',
        "JvmStats": 'tests/unit/liberty_jvm_stats',
        "ThreadPoolStats": 'tests/unit/liberty_thread_pool_stats',
        "SessionStats": 'tests/unit/liberty_session_stats',
        "ConnectionPool": 'tests/unit/liberty_connection_stats'
    }

    return_value = {
        "ServletName":
            '{"value":"JMXRESTProxyServlet","type":"java.lang.String"}',
        "AppName": '{"value":"com.ibm.ws.jmx.connector.server.rest",\
                     "type":"java.lang.String"}',
        "Heap": '{"value":"31588352","type":"java.lang.Long"}',
        "FreeMemory": '{"value":"9104704","type":"java.lang.Long"}',
        "UsedMemory": '{"value":"23213312","type":"java.lang.Long"}',
        "ProcessCPU":
            '{"value":"0.07857719811500322","type":"java.lang.Double"}',
        "GcCount": '{"value":"1325","type":"java.lang.Long"}',
        "GcTime": '{"value":"1001","type":"java.lang.Long"}',
        "UpTime":  '{"value":"155755366","type":"java.lang.Long"}',
        "ActiveThreads": '{"value":"1","type":"java.lang.Integer"}',
        "PoolSize": '{"value":"4","type":"java.lang.Integer"}',
        "PoolName": '{"value":"Default Executor","type":"java.lang.String"}',
        "CreateCount": '{"value":"1","type":"java.lang.Long"}',
        "LiveCount":  '{"value":"0","type":"java.lang.Long"}',
        "ActiveCount": '{"value":"0","type":"java.lang.Long"}',
        "InvalidatedCount": '{"value":"1","type":"java.lang.Long"}',
        "InvalidatedCountbyTimeout": '{"value":"2","type":"java.lang.Long"}',
        "CheckedOutCountValue": '{"value":"1","type":"java.lang.Long"}',
        "WaitQueueSizeValue": '{"value":"2","type":"java.lang.Long"}',
        "MinSizeValue": '{"value":"3","type":"java.lang.Long"}',
        "MaxSizeValue": '{"value":"4","type":"java.lang.Long"}',
        "SizeValue": '{"value":"7","type":"java.lang.Long"}',
        "HostValue": '{"value":"test","type":"java.lang.Long"}',
        "PortValue": '{"value":"12","type":"java.lang.Long"}'
    }

    if last_word in file_value:
        return open(file_value.get(last_word), 'r').read()

    if last_word in return_value:
        return return_value.get(last_word)


class LibertyCrawlTests(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_hundle_ioerror(self):
        with self.assertRaises(CrawlError):
            liberty_crawler.retrieve_status_page("user", "pass", "localhost")

    @mock.patch('urllib2.urlopen', mocked_urllib2_open)
    def test_read(self):
        liberty_crawler.retrieve_status_page("user", "pass", "localhost")
        self.assertNotIsInstance(liberty_crawler.retrieve_metrics(),
                                 feature.LibertyServletFeature)

    @mock.patch('plugins.applications.liberty.'
                'liberty_crawler.retrieve_status_page',
                side_effect=server_status_value)
    def test_ok(self, server_status_value):
        status = list(liberty_crawler.retrieve_metrics())
        assert status == [('liberty_servlet_status',
                           feature.LibertyServletFeature(
                               name='JMXRESTProxyServlet',
                               appName='com.ibm.ws.jmx.connector.server.rest',
                               reqCount='292',
                               responseMean='1646404.6780821919',
                               responseMax='129746827',
                               responseMin='257689'),
                           'application'),
                          ('liberty_jvm_status',
                           feature.LibertyJVMFeature(
                               heap='31588352',
                               freeMemory='9104704',
                               usedMemory='23213312',
                               processCPU='0.07857719811500322',
                               gcCount='1325',
                               gcTime='1001',
                               upTime='155755366'),
                           'application'),
                          ('liberty_thread_status',
                           feature.LibertyThreadFeature(
                               activeThreads='1',
                               poolSize='4',
                               poolName='Default Executor'),
                           'application'),
                          ('liberty_session_status',
                           feature.LibertySessionFeature(
                               name='default_host/IBMJMXConnectorREST',
                               createCount='1',
                               liveCount='0',
                               activeCount='0',
                               invalidatedCount='1',
                               invalidatedCountByTimeout='2'),
                           'application'),
                          ('liberty_mongo_connection_status',
                           feature.LibertyMongoConnectionFeature(
                               checkedOutCount='1',
                               waitQueueSize='2',
                               maxSize='4',
                               minSize='3',
                               host='test',
                               port='12',
                               size='7'),
                           'application')]


class LibertyHostTest(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_get_feature(self):
        c = LibertyHostCrawler()
        self.assertEqual(c.get_feature(), 'liberty')

    @mock.patch('plugins.applications.liberty.'
                'liberty_crawler.retrieve_status_page',
                server_status_value)
    def test_get_metrics(self):
        c = LibertyHostCrawler()
        options = {"password": "password", "user": "liberty"}
        emitted = list(c.crawl(**options))
        self.assertEqual(emitted[0][0], 'liberty_servlet_status')
        self.assertEqual(emitted[0][2], 'application')


class LibertyContainerTest(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_get_feature(self):
        c = LibertyContainerCrawler()
        self.assertEqual(c.get_feature(), 'liberty')

    @mock.patch('plugins.applications.liberty.'
                'liberty_crawler.retrieve_status_page',
                server_status_value)
    @mock.patch('dockercontainer.DockerContainer',
                MockedLibertyContainer1)
    @mock.patch(("plugins.applications.liberty.liberty_container_crawler."
                 "run_as_another_namespace"),
                return_value=['127.0.0.1', '1.2.3.4'])
    def test_liberty_container_forkube(self, *args):
        c = LibertyContainerCrawler()
        options = {"password": "password", "user": "liberty"}
        emitted = list(c.crawl(**options))
        self.assertEqual(emitted[0][0], 'liberty_servlet_status')
        self.assertEqual(emitted[0][2], 'application')

    @mock.patch('plugins.applications.liberty.'
                'liberty_crawler.retrieve_status_page',
                server_status_value)
    @mock.patch('dockercontainer.DockerContainer',
                MockedLibertyContainer2)
    @mock.patch(("plugins.applications.liberty.liberty_container_crawler."
                 "run_as_another_namespace"),
                return_value=['127.0.0.1', '1.2.3.4'])
    def test_liberty_container_fordocker(self, *args):
        c = LibertyContainerCrawler()
        options = {"password": "password", "user": "liberty"}
        emitted = list(c.crawl(**options))
        self.assertEqual(emitted[0][0], 'liberty_servlet_status')
        self.assertEqual(emitted[0][2], 'application')

    @mock.patch('dockercontainer.DockerContainer',
                MockedLibertyContainer3)
    def test_liberty_container_noport(self, *args):
        c = LibertyContainerCrawler()
        c.crawl(1234)
        pass

    @mock.patch('dockercontainer.DockerContainer',
                MockedLibertyContainer1)
    @mock.patch(("plugins.applications.liberty.liberty_container_crawler."
                 "run_as_another_namespace"),
                return_value=['127.0.0.1', '1.2.3.4'])
    @mock.patch('plugins.applications.liberty.'
                'liberty_crawler.retrieve_metrics',
                mock_status_value)
    def test_none_liberty_container(self, *args):
        options = {"password": "password", "user": "liberty"}
        c = LibertyContainerCrawler()
        with self.assertRaises(ConnectionError):
            c.crawl(1234, **options)
