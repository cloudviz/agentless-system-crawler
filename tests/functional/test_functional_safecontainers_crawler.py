import unittest
import docker
import requests.exceptions
import tempfile
import os
import time
import shutil
import subprocess
import sys
import pykafka

# Tests for crawlers in kraken crawlers configuration.

from safe_containers_crawler import SafeContainersCrawler
from worker import Worker
from emitters_manager import EmittersManager
from utils.dockerutils import get_docker_container_rootfs_path

import logging

# Tests conducted with a single container running.


class SafeContainersCrawlerTests(unittest.TestCase):

    def setUp(self):
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        root.addHandler(ch)

        self.docker = docker.APIClient(base_url='unix://var/run/docker.sock',
                                    version='auto')
        try:
            if len(self.docker.containers()) != 0:
                raise Exception(
                    "Sorry, this test requires a machine with no docker"
                    "containers running.")
        except requests.exceptions.ConnectionError:
            print ("Error connecting to docker daemon, are you in the docker"
                   "group? You need to be in the docker group.")

        self.start_crawled_container()

        # start a kakfa+zookeeper container to send data to (to test our
        # kafka emitter)
        self.start_kafka_container()

    def start_kafka_container(self):
        self.docker.pull(repository='spotify/kafka', tag='latest')
        self.kafka_container = self.docker.create_container(
            image='spotify/kafka', ports=[9092, 2181],
            host_config=self.docker.create_host_config(port_bindings={
                9092: 9092,
                2181: 2181
            }),
            environment={'ADVERTISED_HOST': 'localhost',
                         'ADVERTISED_PORT': '9092'})
        self.docker.start(container=self.kafka_container['Id'])

    def start_crawled_container(self):
        # start a container to be crawled
        self.docker.pull(repository='ruby', tag='latest')
        self.container = self.docker.create_container(
            image='ruby:latest', command='tail -f /dev/null',
            ports=[8192],
            host_config=self.docker.create_host_config(port_bindings={
                8192: 8192,
            }),
            environment={'ADVERTISED_HOST': 'localhost',
                         'ADVERTISED_PORT': '8192'})
        self.tempd = tempfile.mkdtemp(prefix='crawlertest.')
        self.docker.start(container=self.container['Id'])
        time.sleep(5)
        rootfs = get_docker_container_rootfs_path(self.container['Id'])
        fd = open(rootfs+'/crawlplugins','w')
        fd.write('cpu\n')
        fd.write('os\n')
        fd.write('memory\n')
        fd.write('interface\n')
        fd.write('process\n')
        fd.write('pythonpackage\n')
        fd.close()

    def tearDown(self):
        self.remove_crawled_container()
        self.remove_kafka_container()

        shutil.rmtree(self.tempd)

    def remove_kafka_container(self):
        self.docker.stop(container=self.kafka_container['Id'])
        self.docker.remove_container(container=self.kafka_container['Id'])

    def remove_crawled_container(self):
        self.docker.stop(container=self.container['Id'])
        self.docker.remove_container(container=self.container['Id'])

    def testCrawlContainer1(self):
        crawler = SafeContainersCrawler(features=[],user_list=self.container['Id'])
        frames = list(crawler.crawl())
        output = str(frames[0])
        print output  # only printed if the test fails
        assert 'interface-lo' in output
        assert 'if_octets_tx' in output
        assert 'cpu-0' in output
        assert 'cpu_nice' in output
        assert 'memory' in output
        assert 'memory_buffered' in output
        assert 'os' in output
        assert 'linux' in output
        assert 'process' in output
        assert 'tail' in output
        assert 'plugincont_user' in output
        assert 'pythonpackage' in output
        assert 'Python' in output

    def testCrawlContainer2(self):
        env = os.environ.copy()
        mypath = os.path.dirname(os.path.realpath(__file__))
        os.makedirs(self.tempd + '/out')

        # crawler itself needs to be root
        process = subprocess.Popen(
            [
                '/usr/bin/python', mypath + '/../../crawler/crawler.py',
                '--url', 'file://' + self.tempd + '/out/crawler',
                '--features', 'none',
                '--crawlContainers', self.container['Id'],
                '--format', 'graphite',
                '--crawlmode', 'OUTCONTAINERSAFE',
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

    def testCrawlContainerKafka(self):
        env = os.environ.copy()
        mypath = os.path.dirname(os.path.realpath(__file__))
        os.makedirs(self.tempd + '/out')

        # crawler itself needs to be root
        process = subprocess.Popen(
            [
                '/usr/bin/python', mypath + '/../../crawler/crawler.py',
                '--url', 'kafka://localhost:9092/test',
                '--features', 'os,process',
                '--crawlContainers', self.container['Id'],
                '--crawlmode', 'OUTCONTAINER',
                '--numprocesses', '1'
            ],
            env=env)
        stdout, stderr = process.communicate()
        assert process.returncode == 0

        print stderr
        print stdout

        kafka = pykafka.KafkaClient(hosts='localhost:9092')
        topic = kafka.topics['test']
        consumer = topic.get_simple_consumer()
        message = consumer.consume()
        assert '"cmd":"tail -f /dev/null"' in message.value
    
    def _testCrawlContainerKafka(self):
        # TODO: verify sandbox restraints here
        pass

if __name__ == '__main__':
    unittest.main()
