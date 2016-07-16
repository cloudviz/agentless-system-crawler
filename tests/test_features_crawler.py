import unittest
import docker
import requests.exceptions
import tempfile
import os
import shutil
import subprocess

from crawler.emitter import Emitter
from crawler.features_crawler import FeaturesCrawler

from crawler.dockercontainer import DockerContainer
from crawler.dockerutils import exec_dockerinspect


# Tests the FeaturesCrawler class
# Throws an AssertionError if any test fails

# Tests conducted with a single container running.
class FeaturesCrawlerTests(unittest.TestCase):
    image_name = 'alpine:latest'

    def setUp(self):
        self.docker = docker.Client(
            base_url='unix://var/run/docker.sock', version='auto')
        try:
            if len(self.docker.containers()) != 0:
                raise Exception(
                    "Sorry, this test requires a machine with no docker containers running.")
        except requests.exceptions.ConnectionError as e:
            print "Error connecting to docker daemon, are you in the docker group? You need to be in the docker group."

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
        crawler = FeaturesCrawler(crawl_mode='INVM')
        cores = len(list(crawler.crawl_cpu()))
        assert cores > 0

    def test_features_crawler_crawl_invm_mem(self):
        crawler = FeaturesCrawler(crawl_mode='INVM')
        cores = len(list(crawler.crawl_memory()))
        assert cores > 0

    def test_features_crawler_crawl_outcontainer_cpu(self):
        c = DockerContainer(self.container['Id'])
        crawler = FeaturesCrawler(crawl_mode='OUTCONTAINER', container=c)
        for key, feature in crawler.crawl_cpu():
            print key, feature
        cores = len(list(crawler.crawl_cpu()))
        assert cores > 0

    def test_features_crawler_crawl_outcontainer_mem(self):
        c = DockerContainer(self.container['Id'])
        crawler = FeaturesCrawler(crawl_mode='OUTCONTAINER', container=c)
        output = "%s" % list(crawler.crawl_memory())
        assert 'memory_used' in output

    if __name__ == '__main__':
        unittest.main()
