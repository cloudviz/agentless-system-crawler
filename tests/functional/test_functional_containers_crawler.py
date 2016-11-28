import unittest
import docker
import requests.exceptions
import tempfile
import os
import shutil
import subprocess
import sys

# Tests for crawlers in kraken crawlers configuration.

from crawler.containers_crawler import ContainersCrawler

import logging

# Tests conducted with a single container running.


class ContainersCrawlerTests(unittest.TestCase):

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

    def testCrawlContainer1(self):
        crawler = ContainersCrawler(features=['cpu', 'memory', 'interface', 'package'])
        frames = list(crawler.crawl())
        output = str(frames[0])
        print output  # only printed if the test fails
        assert 'interface-lo' in output
        assert 'if_octets_tx=' in output
        assert 'cpu-0' in output
        assert 'cpu_nice=' in output
        assert 'memory' in output
        assert 'memory_buffered=' in output
        assert 'apt' in output
        assert 'pkgarchitecture=' in output

    def testCrawlContainer2(self):
        env = os.environ.copy()
        mypath = os.path.dirname(os.path.realpath(__file__))
        os.makedirs(self.tempd + '/out')

        # crawler itself needs to be root
        process = subprocess.Popen(
            [
                '/usr/bin/python', mypath + '/../../crawler/crawler.py',
                '--url', 'file://' + self.tempd + '/out/crawler',
                '--features', 'cpu,memory,interface,package',
                '--crawlContainers', 'ALL',
                '--format', 'graphite',
                '--crawlmode', 'OUTCONTAINER',
                '--numprocesses', '1'
            ],
            env=env)
        stdout, stderr = process.communicate()
        assert process.returncode == 0

        print stderr
        print stdout

        subprocess.call(['/bin/chmod', '-R', '777', self.tempd])

        files = os.listdir(self.tempd + '/out')
        assert len(files) == 1

        f = open(self.tempd + '/out/' + files[0], 'r')
        output = f.read()
        print output  # only printed if the test fails
        assert 'interface-lo.if_octets.tx' in output
        assert 'cpu-0.cpu-idle' in output
        assert 'memory.memory-used' in output
        assert 'apt.pkgsize' in output
        f.close()

    def testCrawlContainer3(self):
        env = os.environ.copy()
        mypath = os.path.dirname(os.path.realpath(__file__))
        os.makedirs(self.tempd + '/out')

        # crawler itself needs to be root
        process = subprocess.Popen(
            [
                '/usr/bin/python', mypath + '/../../crawler/crawler.py',
                '--url', 'file://' + self.tempd + '/out/crawler',
                '--features', 'os,process',
                '--crawlContainers', 'ALL',
                '--crawlmode', 'OUTCONTAINER',
                '--numprocesses', '1'
            ],
            env=env)
        stdout, stderr = process.communicate()
        assert process.returncode == 0

        print stderr
        print stdout

        subprocess.call(['/bin/chmod', '-R', '777', self.tempd])

        files = os.listdir(self.tempd + '/out')
        assert len(files) == 1

        f = open(self.tempd + '/out/' + files[0], 'r')
        output = f.read()
        print output  # only printed if the test fails
        assert 'sleep' in output
        assert 'linux' or 'Linux' in output
        f.close()

    def testCrawlContainerAvoidSetns(self):
        options = {'avoid_setns':True}
        crawler = ContainersCrawler(
            features=['cpu', 'memory', 'interface', 'package'],
            options=options)
        frames = list(crawler.crawl())
        output = str(frames[0])
        print output  # only printed if the test fails
        # interface in avoid_setns mode is not supported
        #assert 'interface-lo' in output
        #assert 'if_octets_tx=' in output
        assert 'cpu-0' in output
        assert 'cpu_nice=' in output
        assert 'memory' in output
        assert 'memory_buffered=' in output
        assert 'apt' in output
        assert 'pkgarchitecture=' in output

if __name__ == '__main__':
    unittest.main()
