from __future__ import print_function
import unittest
import sys
import mock
sys.path.append('tests/unit/')
sys.modules['pynvml'] = __import__('mock_pynvml')
from plugins.systems.gpu_host_crawler import GPUHostCrawler

class GPUPluginTests(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    @mock.patch(
        'plugins.systems.gpu_host_crawler.get_host_ipaddr',
        side_effect=lambda: "127.0.0.1")
    @mock.patch(
        'plugins.systems.gpu_host_crawler.GPUHostCrawler._load_nvidia_lib',
        side_effect=lambda: 1)
    def test_os_gpu_host_crawler_plugin(self, *args):
        fc = GPUHostCrawler()
        for gpu_metrics in fc.crawl():
            print(gpu_metrics)
            assert gpu_metrics == (
                '127/0/0/1.gpu0.NA.NA',
                {
                    "memory": {"total": 12205, "used": 0, "free": 12205},
                    "temperature": 31,
                    "power": {"draw": 27, "limit": 149},
                    "utilization": {"gpu": 0, "memory": 0}
                },
                'gpu')            
