import mock
import unittest
import os

from crawler.mtgraphite import MTGraphiteClient
from crawler.crawler_exceptions import MTGraphiteInvalidTenant

class MockedSocket:
    def settimeout(self, n):
        pass
    def write(self, str):
        return len(str)

class MockedConnection:
    def __init__(self):
        print 'init mocked connection'
    def connect(self, *args):
        pass
    def getsockname(self):
        return ['host']
    def close(self):
        pass
    def write(self, str):
        return len(str)
    def read(self, n):
        return '1A' * n

class MockedConnectionBadPassword:
    def __init__(self):
        print 'init mocked connection'
    def connect(self, *args):
        pass
    def getsockname(self):
        return ['host']
    def close(self):
        pass
    def write(self, str):
        return len(str)
    def read(self, n):
        return '0A' * n # bad password

class MTGraphiteTests(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    @mock.patch('crawler.mtgraphite.time.time', side_effect=lambda : 1000)
    def test_init(self, *args):
        mt = MTGraphiteClient('mtgraphite://2.2.2.2:123/crawler:password',
                              batch_send_every_t=1,
                              batch_send_every_n=10)
        assert not mt.conn
        assert not mt.socket
        assert mt.next_timeout == 1001
        assert mt.host == '2.2.2.2'
        assert mt.port == '123'
        assert mt.tenant == 'crawler'
        assert mt.password == 'password'
        args[0].assert_called()

    @mock.patch('crawler.mtgraphite.time.time', side_effect=lambda : 1000)
    def test_init_bad_urls(self, *args):

        with self.assertRaises(ValueError):
            mt = MTGraphiteClient('mtgraphite://2.2.2.2:123/crawler')
        with self.assertRaises(ValueError):
            mt = MTGraphiteClient('mtgraphite://2.2.2.2:123/:password')
        with self.assertRaises(ValueError):
            mt = MTGraphiteClient('mtgraphite://2.2.2.2:123/')
        with self.assertRaises(ValueError):
            mt = MTGraphiteClient('mtgraphite://2.2.2.2:123')
        with self.assertRaises(ValueError):
            mt = MTGraphiteClient('mtgraphite://2.2.2.2')
        with self.assertRaises(ValueError):
            mt = MTGraphiteClient('mtgraphite://2.2.2.2/crawler')
        with self.assertRaises(ValueError):
            mt = MTGraphiteClient('mtgraphite://2.2.2.2/crawler:password')
        with self.assertRaises(ValueError):
            mt = MTGraphiteClient('mtgraphite://:234/crawler:password')
        with self.assertRaises(ValueError):
            mt = MTGraphiteClient('mtgraphite://')
        with self.assertRaises(ValueError):
            mt = MTGraphiteClient('http://1.2.3.4:234/crawler:password')
        with self.assertRaises(ValueError):
            mt = MTGraphiteClient('host.com:234/crawler:password')
        with self.assertRaises(ValueError):
            mt = MTGraphiteClient('host')
        mt = MTGraphiteClient('mtgraphite://host.com:234/crawler:password')

    @mock.patch('crawler.mtgraphite.time.sleep')
    @mock.patch('crawler.mtgraphite.time.time', side_effect=lambda : 1000)
    @mock.patch('crawler.mtgraphite.socket.socket',
                side_effect=lambda a, b: MockedSocket())
    @mock.patch('crawler.mtgraphite.ssl.wrap_socket',
                side_effect=lambda s, cert_reqs : MockedConnection())
    def test_send(self, *args):
        mt = MTGraphiteClient('mtgraphite://2.2.2.2:123/crawler:password',
                              batch_send_every_t=1000,
                              batch_send_every_n=3)
        assert mt.next_timeout == 2000

        with self.assertRaises(TypeError):
            mt.send_messages(1)

        m1 = mt.construct_message('space', 'group', 'cpu', 100, 1)
        m2 = mt.construct_message('space', 'group', 'cpu', 100, 2)

        with self.assertRaises(TypeError):
            mt.send_messages(m1)

        # we will not send anything yet as send_every_n is 3
        mt.send_messages([m1, m2])
        assert mt.msgset == [m1, m2]

        # now we should send something
        m3 = mt.construct_message('space', 'group', 'cpu', 100, 3)
        mt.send_messages([m3])
        assert mt.msgset == []

        mt.close()
        assert mt.conn == None

    @mock.patch('crawler.mtgraphite.time.sleep')
    @mock.patch('crawler.mtgraphite.time.time', side_effect=lambda : 1000)
    @mock.patch('crawler.mtgraphite.socket.socket',
                side_effect=lambda a, b: MockedSocket())
    @mock.patch('crawler.mtgraphite.ssl.wrap_socket',
                side_effect=lambda s, cert_reqs : MockedConnectionBadPassword())
    def test_send_bad_password(self, *args):
        mt = MTGraphiteClient('mtgraphite://2.2.2.2:123/crawler:password',
                              batch_send_every_t=1000,
                              batch_send_every_n=3)
        assert mt.next_timeout == 2000

        m1 = mt.construct_message('space', 'group', 'cpu', 100, 1)
        m2 = mt.construct_message('space', 'group', 'cpu', 100, 2)
        m3 = mt.construct_message('space', 'group', 'cpu', 100, 3)

        with self.assertRaises(MTGraphiteInvalidTenant):
            mt.send_messages([m1, m2, m3])

        assert mt.msgset == [m1, m2, m3]
