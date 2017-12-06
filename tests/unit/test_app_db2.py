import mock
import pip
from unittest import TestCase
from plugins.applications.db2 import db2_crawler
from plugins.applications.db2.feature import DB2Feature
from plugins.applications.db2.db2_container_crawler \
    import DB2ContainerCrawler
from plugins.applications.db2.db2_host_crawler \
    import DB2HostCrawler
from utils.crawler_exceptions import CrawlError
from requests.exceptions import ConnectionError


pip.main(['install', 'ibm_db'])


class MockedDB2Container1(object):

    def __init__(self, container_id):
        ports = "[ {\"containerPort\" : \"50000\"} ]"
        self.inspect = {"State": {"Pid": 1234}, "Config": {"Labels":
                                                           {"annotation.io.kubernetes.container.ports": ports}}}


class MockedDB2Container2(object):

    def __init__(self, container_id):
        self.inspect = {"State": {"Pid": 1234},
                        "Config": {"Labels": {"dummy": "dummy"}}}

    def get_container_ports(self):
        ports = ["50000"]
        return ports


class MockedDB2Container3(object):

    def __init__(self, container_id):
        self.inspect = {"State": {"Pid": 1234},
                        "Config": {"Labels": {"dummy": "dummy"}}}

    def get_container_ports(self):
        ports = ["1234"]
        return ports


def mocked_dbi_conn_error(ibm_db_conn):
    raise Exception("error")


def mocked_dbi_conn(ibm_db_conn):
    return


def mocked_db_exec_error(sql):
    raise Exception("error")


def mocked_db_conn(req, opt1, opt2):
    return


def mocked_ibm_db_dbi_conn(object):
    conn = mocked_conn()
    return conn


class mocked_conn():
    def cursor(obj):
        return

    def execute(sql):
        return


def mocked_retrieve_metrics(host, user, password, db):

    attribute = DB2Feature(
        "dbCapacity",
        "dbVersion",
        "instanceName",
        "productName",
        "dbName",
        "serviceLevel",
        "instanceConn",
        "instanceUsedMem",
        "dbConn",
        "usedLog",
        "transcationInDoubt",
        "xlocksEscalation",
        "locksEscalation",
        "locksTimeOut",
        "deadLock",
        "lastBackupTime",
        "dbStatus",
        "instanceStatus",
        "bpIndexHitRatio",
        "bpDatahitRatio",
        "sortsInOverflow",
        "agetnsWait",
        "updateRows",
        "insertRows",
        "selectedRows",
        "deleteRows",
        "selects",
        "selectSQLs",
        "dynamicSQLs",
        "rollbacks",
        "commits",
        "bpTempIndexHitRatio",
        "bpTempDataHitRatio"
    )

    return attribute


def mocked_retrieve_metrics_error(host, user, password, db):
    raise CrawlError


class DB2CrawlTests(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    @mock.patch('ibm_db_dbi.Connection', mocked_dbi_conn_error)
    def test_conn_error(self):
        with self.assertRaises(CrawlError):
            db2_crawler.retrieve_metrics()

    @mock.patch('ibm_db.connect', mocked_db_conn)
    @mock.patch('ibm_db_dbi.Connection', mocked_ibm_db_dbi_conn)
    @mock.patch('ibm_db.execute', mocked_dbi_conn_error)
    def test_exec_error(self):
        with self.assertRaises(CrawlError):
            db2_crawler.retrieve_metrics()

    @mock.patch('ibm_db.connect', mocked_db_conn)
    @mock.patch('ibm_db_dbi.Connection')
    def test_ok(self, mock_connect):
        status = db2_crawler.retrieve_metrics()
        self.assertIsInstance(status, DB2Feature)


class DB2HostTest(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_get_feature(self):
        c = DB2HostCrawler()
        self.assertEqual(c.get_feature(), 'db2')

    @mock.patch('plugins.applications.db2.'
                'db2_crawler.retrieve_metrics',
                mocked_retrieve_metrics)
    def test_get_metrics(self):
        c = DB2HostCrawler()
        options = {"password": "password", "user": "db2inst1", "db": "sample"}
        emitted = c.crawl(**options)[0]
        self.assertEqual(emitted[0], 'db2')
        self.assertIsInstance(emitted[1], DB2Feature)
        self.assertEqual(emitted[2], 'application')

    @mock.patch('plugins.applications.db2.'
                'db2_crawler.retrieve_metrics',
                mocked_retrieve_metrics_error)
    def test_get_metrics_error(self):
        with self.assertRaises(CrawlError):
            c = DB2HostCrawler()
            c.crawl()[0]


class DB2ContainerTest(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_get_feature(self):
        c = DB2ContainerCrawler()
        self.assertEqual(c.get_feature(), 'db2')

    @mock.patch('plugins.applications.db2.'
                'db2_crawler.retrieve_metrics',
                mocked_retrieve_metrics)
    @mock.patch('dockercontainer.DockerContainer',
                MockedDB2Container1)
    @mock.patch(("plugins.applications.db2.db2_container_crawler."
                 "run_as_another_namespace"),
                return_value=['127.0.0.1', '1.2.3.4'])
    def test_db2_container_crawler_forkube(self, *kwargs):
        c = DB2ContainerCrawler()
        options = {"password": "password", "user": "db2inst1", "db": "sample"}
        emitted = c.crawl(1234, **options)[0]
        self.assertEqual(emitted[0], 'db2')
        self.assertIsInstance(emitted[1], DB2Feature)
        self.assertEqual(emitted[2], 'application')

    @mock.patch('plugins.applications.db2.'
                'db2_crawler.retrieve_metrics',
                mocked_retrieve_metrics)
    @mock.patch('dockercontainer.DockerContainer',
                MockedDB2Container2)
    @mock.patch(("plugins.applications.db2.db2_container_crawler."
                 "run_as_another_namespace"),
                return_value=['127.0.0.1', '1.2.3.4'])
    def test_db2_container_crawler_fordocker(self, *kwargs):
        c = DB2ContainerCrawler()
        options = {"password": "password", "user": "db2inst1", "db": "sample"}
        emitted = c.crawl(1234, **options)[0]
        self.assertEqual(emitted[0], 'db2')
        self.assertIsInstance(emitted[1], DB2Feature)
        self.assertEqual(emitted[2], 'application')

    @mock.patch('dockercontainer.DockerContainer',
                MockedDB2Container3)
    def test_no_available_port(self):
        c = DB2ContainerCrawler()
        c.crawl("mockcontainer")
        pass

    @mock.patch('plugins.applications.db2.'
                'db2_crawler.retrieve_metrics',
                mocked_retrieve_metrics_error)
    @mock.patch('dockercontainer.DockerContainer',
                MockedDB2Container2)
    @mock.patch(("plugins.applications.db2.db2_container_crawler."
                 "run_as_another_namespace"),
                return_value=['127.0.0.1', '1.2.3.4'])
    def test_no_accessible_endpoint(self, *args):
        c = DB2ContainerCrawler()
        with self.assertRaises(ConnectionError):
            options = {"password": "password",
                       "user": "db2inst1", "db": "sample"}
            c.crawl(1234, **options)[0]
