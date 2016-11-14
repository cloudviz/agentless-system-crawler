import unittest
import docker
import requests.exceptions
import tempfile
import shutil

from crawler.plugins.cpu_host_crawler import CpuHostCrawler
from crawler.plugins.memory_host_crawler import MemoryHostCrawler

from crawler.plugins.cpu_container_crawler import CpuContainerCrawler
from crawler.plugins.memory_container_crawler import MemoryContainerCrawler
from crawler.plugins.os_container_crawler import OSContainerCrawler
from crawler.plugins.process_container_crawler import ProcessContainerCrawler

# Tests the FeaturesCrawler class
# Throws an AssertionError if any test fails


# Tests conducted with a single container running.
class HostAndContainerPluginsFunctionalTests(unittest.TestCase):
    image_name = 'alpine:latest'

    def setUp(self):
        self.docker = docker.Client(
            base_url='unix://var/run/docker.sock', version='auto')
        try:
            if len(self.docker.containers()) != 0:
                raise Exception(
                    "Sorry, this test requires a machine with no docker"
                    "containers running.")
        except requests.exceptions.ConnectionError:
            print ("Error connecting to docker daemon, are you in the docker"
                   "group? You need to be in the docker group.")

        self.docker.pull(repository='alpine', tag='latest')
        self.container = self.docker.create_container(
            image=self.image_name, command='/bin/sleep 60')
        self.tempd = tempfile.mkdtemp(prefix='crawlertest.')
        self.docker.start(container=self.container['Id'])

    def tearDown(self):
        self.docker.stop(container=self.container['Id'])
        self.docker.remove_container(container=self.container['Id'])

        shutil.rmtree(self.tempd)

    def test_features_crawler_crawl_invm_cpu(self):
        fc = CpuHostCrawler()
        cores = len(list(fc.crawl()))
        assert cores > 0

    def test_features_crawler_crawl_invm_mem(self):
        fc = MemoryHostCrawler()
        cores = len(list(fc.crawl()))
        assert cores > 0

    def test_features_crawler_crawl_outcontainer_cpu(self):
        fc = CpuContainerCrawler()
        for key, feature, t in fc.crawl(self.container['Id']):
            print key, feature
        cores = len(list(fc.crawl(self.container['Id'])))
        assert cores > 0

    def test_features_crawler_crawl_outcontainer_os(self):
        fc = OSContainerCrawler()
        assert len(list(fc.crawl(self.container['Id']))) == 1

    def test_features_crawler_crawl_outcontainer_processes(self):
        fc = ProcessContainerCrawler()
        # sleep + crawler
        assert len(list(fc.crawl(self.container['Id']))) == 2

    def test_features_crawler_crawl_outcontainer_mem(self):
        fc = MemoryContainerCrawler()
        output = "%s" % list(fc.crawl(self.container['Id']))
        assert 'memory_used' in output

    if __name__ == '__main__':
        unittest.main()
