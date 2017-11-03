import unittest
import sys
import mock
sys.path.append('tests/unit/')
sys.modules['pynvml'] = __import__('mock_pynvml')
from plugins.systems.gpu_host_crawler import GPUHostCrawler

def mocked_util():
    return "127.0.0.1"

class GPUPluginTests(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    @mock.patch(
        'plugins.systems.gpu_host_crawler.GPUHostCrawler._load_nvidia_lib',
        side_effect=lambda: 1)
    @mock.patch('utils.misc.get_host_ipaddr',side_effect=mocked_util)
    def test_os_gpu_host_crawler_plugin(self, *args):
        fc = GPUHostCrawler()
        for gpu_metrics in fc.crawl():
            print gpu_metrics
            assert 'gpu0.NA' in gpu_metrics[0]
            assert gpu_metrics[1] == '
                {
                    "memory": {"total": 12205, "used": 0, "free": 12205},
                    "temperature": 31,
                    "power": {"draw": 27, "limit": 149},
                    "utilization": {"gpu": 0, "memory": 0}
                }'
            assert gpu_metric[2] == 'gpu'
