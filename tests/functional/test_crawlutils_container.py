import unittest
import docker
import requests.exceptions
import tempfile
import os
import shutil
import subprocess
import sys

# Tests for crawlers in kraken crawlers configuration.

import crawler.crawlutils

import logging

# Tests conducted with a single container running.


class CrawlutilsContainerTests(unittest.TestCase):

    def setUp(self):
        root = logging.getLogger()
        root.setLevel(logging.DEBUG)
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        root.addHandler(ch)

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

        self.docker.pull(repository='ubuntu', tag='latest')
        self.container = self.docker.create_container(
            image='ubuntu:latest', command='/bin/sleep 60')
        self.tempd = tempfile.mkdtemp(prefix='crawlertest.')
        self.docker.start(container=self.container['Id'])

    def tearDown(self):
        self.docker.stop(container=self.container['Id'])
        self.docker.remove_container(container=self.container['Id'])

        shutil.rmtree(self.tempd)

    def testCrawlContainer(self):
        os.makedirs(self.tempd + '/out')

        features = ['cpu', 'memory', 'interface', 'package']
        crawler.plugins_manager.reload_container_crawl_plugins(
            features=features)
        crawler.crawlutils.snapshot_container(
            urls=[
                'file://' + self.tempd + '/out/crawler'],
            features=features,
            format='graphite',
            container=crawler.dockercontainer.DockerContainer(
                self.container['Id']))

        subprocess.call(['/bin/chmod', '-R', '777', self.tempd])

        files = os.listdir(self.tempd + '/out')
        assert len(files) == 1

        f = open(self.tempd + '/out/' + files[0], 'r')
        output = f.read()
        print output  # only printed if the test fails
        assert 'interface-lo.if_octets.tx' in output
        assert 'cpu-0.cpu-idle' in output
        assert 'memory.memory-used' in output
        assert 'pkgsize' in output
        f.close()

    def testCrawlInVm(self):
        os.makedirs(self.tempd + '/out')

        features = ['cpu', 'memory', 'interface', 'package']
        crawler.plugins_manager.reload_host_crawl_plugins(features=features)
        crawler.crawlutils.snapshot_generic(
            namespace='random_namespace',
            urls=['file://' + self.tempd + '/out/crawler'],
            features=features,
            format='graphite',
        )

        subprocess.call(['/bin/chmod', '-R', '777', self.tempd])

        files = os.listdir(self.tempd + '/out')
        assert len(files) == 1

        f = open(self.tempd + '/out/' + files[0], 'r')
        output = f.read()
        print output  # only printed if the test fails
        assert 'interface-lo.if_octets.tx' in output
        assert 'cpu-0.cpu-idle' in output
        assert 'memory.memory-used' in output
        assert 'pkgsize' in output
        f.close()
