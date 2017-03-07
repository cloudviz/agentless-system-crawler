import mock
from unittest import TestCase
from plugins.applications.db2 import db2_crawler
from plugins.applications.db2.feature import DB2Feature
from plugins.applications.db2.db2_container_crawler \
    import DB2ContainerCrawler
from plugins.applications.db2.db2_host_crawler \
    import DB2HostCrawler
from utils.crawler_exceptions import CrawlError


class MockedNoNameContainer(object):

    def __init__(self, container_id):
        self.image_name = 'dummy'


class MockedNoPortContainer(object):

    def __init__(
            self,
            container_id,
    ):
        self.image_name = 'db2'

    def get_container_ip(self):
        return '1.2.3.4'

    def get_container_ports(self):
        ports = []
        return ports


class MockedDB2Container(object):

    def __init__(
            self,
            container_id,
    ):
        self.image_name = 'db2'

    def get_container_ip(self):
        return '1.2.3.4'

    def get_container_ports(self):
        ports = [500001, 500000]
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
                MockedDB2Container)
    def test_get_metrics(self):
        c = DB2ContainerCrawler()
        options = {"password": "password", "user": "db2inst1", "db": "sample"}
        emitted = c.crawl(**options)[0]
        self.assertEqual(emitted[0], 'db2')
        self.assertIsInstance(emitted[1], DB2Feature)
        self.assertEqual(emitted[2], 'application')

    @mock.patch('dockercontainer.DockerContainer',
                MockedNoPortContainer)
    def test_no_available_port(self):
        c = DB2ContainerCrawler()
        with self.assertRaises(CrawlError):
            c.crawl("mockcontainer")

    @mock.patch('dockercontainer.DockerContainer',
                MockedNoNameContainer)
    def test_none_apache_container(self):
        c = DB2ContainerCrawler()
        with self.assertRaises(CrawlError):
            c.crawl("mockcontainer")

    @mock.patch('plugins.applications.db2.'
                'db2_crawler.retrieve_metrics',
                mocked_retrieve_metrics_error)
    @mock.patch('dockercontainer.DockerContainer',
                MockedDB2Container)
    def test_no_accessible_endpoint(self):
        c = DB2ContainerCrawler()
        with self.assertRaises(CrawlError):
            c.crawl("mockcontainer")
