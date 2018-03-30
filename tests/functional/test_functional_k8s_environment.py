import unittest
import docker
import requests.exceptions
import tempfile
import os
import shutil
import subprocess
import sys
import json

# Tests for crawlers in kubernetes crawlers configuration.

from containers_crawler import ContainersCrawler
from worker import Worker
from emitters_manager import EmittersManager

import logging

# Tests conducted with a single container running.

CONT_NAME = "io.kubernetes.container.name"
POD_NAME = "io.kubernetes.pod.name"
POD_UID = "io.kubernetes.pod.uid"
POD_NS = "io.kubernetes.pod.namespace"
K8S_DELIMITER = "/"


class ContainersCrawlerTests(unittest.TestCase):

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
        self.k8s_labels = dict()
        self.k8s_labels[CONT_NAME] = "simson"
        self.k8s_labels[POD_NAME] = "pod-test"
        self.k8s_labels[POD_UID] = "pod-123"
        self.k8s_labels[POD_NS] = "devtest"
        try:
            if len(self.docker.containers()) != 0:
                raise Exception(
                    "Sorry, this test requires a machine with no docker"
                    "containers running.")
        except requests.exceptions.ConnectionError:
            print ("Error connecting to docker daemon, are you in the docker"
                   "group? You need to be in the docker group.")

        self.start_crawled_container()

    def start_crawled_container(self):
        # start a container to be crawled
        self.docker.pull(repository='ubuntu', tag='latest')
        self.container = self.docker.create_container(
            image='ubuntu:latest', labels=self.k8s_labels, command='/bin/sleep 60')
        self.tempd = tempfile.mkdtemp(prefix='crawlertest.')
        self.docker.start(container=self.container['Id'])

    def tearDown(self):
        self.remove_crawled_container()

        shutil.rmtree(self.tempd)

    def remove_crawled_container(self):
        self.docker.stop(container=self.container['Id'])
        self.docker.remove_container(container=self.container['Id'])

    def testCrawlContainer1(self):
        crawler = ContainersCrawler(
            features=[
                'cpu',
                'memory',
                'interface',
                'package'],
            environment='kubernetes')
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

    '''
    Test for graphite o/p format.
    '''

    def testCrawlContainer2(self):
        env = os.environ.copy()
        mypath = os.path.dirname(os.path.realpath(__file__))
        os.makedirs(self.tempd + '/out')

        # crawler itself needs to be root
        process = subprocess.Popen(
            [
                '/usr/bin/python', mypath + '/../../crawler/crawler.py',
                '--url', 'file://' + self.tempd + '/out/crawler',
                '--features', 'cpu,memory,interface',
                '--crawlContainers', self.container['Id'],
                '--format', 'graphite',
                '--crawlmode', 'OUTCONTAINER',
                '--environment', 'kubernetes',
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
        sample_out = output.split('\n')[0]
        print sample_out
        namespace_parts = sample_out.split(".")[:4]
        assert len(namespace_parts) == 4
        assert namespace_parts[0] == self.k8s_labels[POD_NS]
        assert namespace_parts[1] == self.k8s_labels[POD_NAME]
        assert namespace_parts[2] == self.k8s_labels[CONT_NAME]
        assert 'interface-lo.if_octets.tx' in output
        assert 'cpu-0.cpu-idle' in output
        assert 'memory.memory-used' in output
        f.close()

    '''
    Test for csv o/p format
    '''

    def testCrawlContainer3(self):
        env = os.environ.copy()
        mypath = os.path.dirname(os.path.realpath(__file__))
        os.makedirs(self.tempd + '/out')

        # crawler itself needs to be root
        process = subprocess.Popen(
            [
                '/usr/bin/python', mypath + '/../../crawler/crawler.py',
                '--url', 'file://' + self.tempd + '/out/crawler',
                '--features', 'cpu,memory,interface',
                '--crawlContainers', self.container['Id'],
                '--format', 'csv',
                '--crawlmode', 'OUTCONTAINER',
                '--environment', 'kubernetes',
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
        metadata_frame = output.split('\n')[0]
        metadata_str = metadata_frame.split()[2]
        metadata_json = json.loads(metadata_str)
        namespace_str = metadata_json['namespace']
        assert namespace_str
        namespace_parts = namespace_str.split(K8S_DELIMITER)
        assert len(namespace_parts) == 4
        assert namespace_parts[0] == self.k8s_labels[POD_NS]
        assert namespace_parts[1] == self.k8s_labels[POD_NAME]
        assert namespace_parts[2] == self.k8s_labels[CONT_NAME]
        assert 'interface-lo' in output
        assert 'cpu-0' in output
        assert 'memory' in output
        f.close()

    '''
    Test for json o/p format
    '''

    def testCrawlContainer4(self):
        env = os.environ.copy()
        mypath = os.path.dirname(os.path.realpath(__file__))
        os.makedirs(self.tempd + '/out')

        # crawler itself needs to be root
        process = subprocess.Popen(
            [
                '/usr/bin/python', mypath + '/../../crawler/crawler.py',
                '--url', 'file://' + self.tempd + '/out/crawler',
                '--features', 'cpu,memory,interface',
                '--crawlContainers', self.container['Id'],
                '--format', 'json',
                '--crawlmode', 'OUTCONTAINER',
                '--environment', 'kubernetes',
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
        sample_out = output.split('\n')[0]
        metadata_json = json.loads(sample_out)
        namespace_str = metadata_json['namespace']
        assert namespace_str
        namespace_parts = namespace_str.split(K8S_DELIMITER)
        assert len(namespace_parts) == 4
        assert namespace_parts[0] == self.k8s_labels[POD_NS]
        assert namespace_parts[1] == self.k8s_labels[POD_NAME]
        assert namespace_parts[2] == self.k8s_labels[CONT_NAME]
        assert 'memory_used' in output
        assert 'if_octets_tx' in output
        assert 'cpu_idle' in output
        f.close()


if __name__ == '__main__':
    unittest.main()
