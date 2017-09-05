import unittest
import sys
sys.path.append('tests/unit/')
sys.modules['pynvml'] = __import__('mock_pynvml')

from plugins.systems.gpu_host_crawler import GPUHostCrawler

class GPUPluginTests(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_os_gpu_host_crawler_plugin(self, *args):
        fc = GPUHostCrawler()
        for gpu_metrics in fc.crawl():
            print gpu_metrics
            assert gpu_metrics == (
                'gpu0',
                {
                    "memory":{"total":12205,"used":0,"free":12205},
                    "temperature":31,
                    "power":{"draw":27,"limit":149},
                    "utilization":{"gpu":0,"memory":0}
                },
                'gpu')



