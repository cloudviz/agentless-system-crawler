import mock
from unittest import TestCase
from crawler.plugins.applications.redis.feature import RedisFeature
from crawler.plugins.applications.redis.redis_host_crawler \
    import RedisHostCrawler
from crawler.plugins.applications.redis.redis_container_crawler \
    import RedisContainerCrawler
from requests.exceptions import ConnectionError


class MockedRedisClient(object):

    def __init__(self, host='localhost', port=6379):
        self.host = host
        self.port = port

    def info(self):
        metrics = {
            "aof_current_rewrite_time_sec": -1,
            "aof_enabled": 0,
            "aof_last_bgrewrite_status": "ok",
            "aof_last_rewrite_time_sec": -1,
            "aof_last_write_status": "ok",
            "aof_rewrite_in_progress": 0,
            "aof_rewrite_scheduled": 0,
            "arch_bits": 64,
            "blocked_clients": 0,
            "client_biggest_input_buf": 0,
            "client_longest_output_list": 0,
            "cluster_enabled": 0,
            "config_file": "",
            "connected_clients": 1,
            "connected_slaves": 0,
            "evicted_keys": 0,
            "executable": "/data/redis-server",
            "expired_keys": 0,
            "gcc_version": "4.9.2",
            "hz": 10,
            "instantaneous_input_kbps": 0.0,
            "instantaneous_ops_per_sec": 0,
            "instantaneous_output_kbps": 0.0,
            "keyspace_hits": 0,
            "keyspace_misses": 0,
            "latest_fork_usec": 0,
            "loading": 0,
            "lru_clock": 3053805,
            "master_repl_offset": 0,
            "maxmemory": 0,
            "maxmemory_human": "0B",
            "maxmemory_policy": "noeviction",
            "mem_allocator": "jemalloc-4.0.3",
            "mem_fragmentation_ratio": 8.18,
            "migrate_cached_sockets": 0,
            "multiplexing_api": "epoll",
            "os": "Linux 4.4.0-21-generic ppc64le",
            "process_id": 1,
            "pubsub_channels": 0,
            "pubsub_patterns": 0,
            "rdb_bgsave_in_progress": 0,
            "rdb_changes_since_last_save": 0,
            "rdb_current_bgsave_time_sec": -1,
            "rdb_last_bgsave_status": "ok",
            "rdb_last_bgsave_time_sec": -1,
            "rdb_last_save_time": 1479217974,
            "redis_build_id": "962858415ee795a5",
            "redis_git_dirty": 0,
            "redis_git_sha1": 0,
            "redis_mode": "standalone",
            "redis_version": "3.2.0",
            "rejected_connections": 0,
            "repl_backlog_active": 0,
            "repl_backlog_first_byte_offset": 0,
            "repl_backlog_histlen": 0,
            "repl_backlog_size": 1048576,
            "role": "master",
            "run_id": "7b9a920c40761ad5750fbc8810408b69eca45c06",
            "sync_full": 0,
            "sync_partial_err": 0,
            "sync_partial_ok": 0,
            "tcp_port": 6379,
            "total_commands_processed": 108,
            "total_connections_received": 109,
            "total_net_input_bytes": 1526,
            "total_net_output_bytes": 228594,
            "total_system_memory": 8557363200,
            "total_system_memory_human": "7.97G",
            "uptime_in_days": 2,
            "uptime_in_seconds": 230839,
            "used_cpu_sys": 86.48,
            "used_cpu_sys_children": 0.0,
            "used_cpu_user": 25.17,
            "used_cpu_user_children": 0.0,
            "used_memory": 856848,
            "used_memory_peak": 857872,
            "used_memory_peak_human": "837.77K",
            "used_memory_rss": 7012352,
            "used_memory_rss_human": "6.69M"
        }
        return metrics


class MockedRedisClient2(object):

    def __init__(self, host='localhost', port=6379):
        self.host = host
        self.port = port

    def info(self):
        raise ConnectionError()


class MockedRedisContainer1(object):

    def __init__(
            self,
            container_id,
    ):
        self.image_name = 'redis-container'

    def get_container_ip(self):
        return "1.2.3.4"

    def get_container_ports(self):
        ports = ["6379"]
        return ports


class MockedRedisContainer2(object):

    def __init__(
            self,
            container_id,
    ):
        self.image_name = 'dummy'

    def get_container_ip(self):
        return "1.2.3.4"

    def get_container_ports(self):
        ports = ["6379"]
        return ports


class MockedRedisContainer3(object):

    def __init__(
            self,
            container_id,
    ):
        self.image_name = 'redis-no-ports'

    def get_container_ip(self):
        return "1.2.3.4"

    def get_container_ports(self):
        ports = []
        return ports


class MockedRedisContainer4(object):

    def __init__(
            self,
            container_id,
    ):
        self.image_name = 'redis-no-ports'

    def get_container_ip(self):
        return "1.2.3.4"

    def get_container_ports(self):
        ports = ["80", "8080"]
        return ports


class RedisModuleTests(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_redis_module(self):
        import redis
        v = redis.VERSION
        self.assertIsNotNone(v, "redis module does not exist")


class RedisContainerCrawlTests(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_get_feature(self):
        c = RedisContainerCrawler()
        self.assertEqual(c.get_feature(), "application")

    @mock.patch('crawler.dockercontainer.DockerContainer',
                MockedRedisContainer1)
    @mock.patch('redis.Redis', MockedRedisClient)
    def test_redis_container_crawler(self):
        c = RedisContainerCrawler()
        emitted_tuple = c.crawl("mockcontainerid")[0]
        self.assertEqual(emitted_tuple[0], "redis",
                         "feature key must be equal to redis")
        self.assertIsInstance(emitted_tuple[1], RedisFeature)
        self.assertEqual(emitted_tuple[2], "application",
                         "feature type must be equal to application")

    @mock.patch('crawler.dockercontainer.DockerContainer',
                MockedRedisContainer2)
    def test_none_redis_container_crawler(self):
        c = RedisContainerCrawler()
        with self.assertRaises(NameError):
            c.crawl("mockcontainerid")

    @mock.patch('crawler.dockercontainer.DockerContainer',
                MockedRedisContainer4)
    @mock.patch('redis.Redis', MockedRedisClient2)
    def test_no_available_ports(self):
        c = RedisContainerCrawler()
        with self.assertRaises(ConnectionError):
            c.crawl("mockcontainerid")

    @mock.patch('crawler.dockercontainer.DockerContainer',
                MockedRedisContainer3)
    @mock.patch('redis.Redis', MockedRedisClient)
    def test_set_default_port(self):
        c = RedisContainerCrawler()
        emitted_tuple = c.crawl("mockcontainerid")[0]
        self.assertEqual(emitted_tuple[0], "redis",
                         "feature key must be equal to redis")


class RedisHostCrawlTests(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_get_feature(self):
        c = RedisHostCrawler()
        self.assertEqual(c.get_feature(), "application")

    def test_redis_host_crawler(self):
        with mock.patch('redis.Redis', MockedRedisClient):
            c = RedisHostCrawler()
            emitted_tuple = c.crawl()[0]
            self.assertEqual(emitted_tuple[0], "redis",
                             "feature key must be equal to redis")
            self.assertIsInstance(emitted_tuple[1], RedisFeature)
            self.assertEqual(emitted_tuple[2], "application",
                             "feature type must be equal to application")

    @mock.patch('redis.Redis', MockedRedisClient2)
    def test_no_redis_connection(self):
        c = RedisHostCrawler()
        with self.assertRaises(ConnectionError):
            c.crawl()
