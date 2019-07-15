import unittest
import docker
import os
import subprocess

class CrawlerCosEmitterTests(unittest.TestCase):

    def setUp(self):
        self.docker = docker.Client(
            base_url='unix://var/run/docker.sock', version='auto')

        self.start_minio_container()
        self.start_crawled_container()

    def tearDown(self):
        containers = self.docker.containers()
        for container in containers:
            self.docker.stop(container=container['Id'])
            self.docker.remove_container(container=container['Id'])

    def start_minio_container(self):    
        self.docker.pull(repository='shri4u/minio2', tag='latest')
        self.minio_container = self.docker.create_container(
            image='shri4u/minio2', ports=[9000],
            host_config=self.docker.create_host_config(port_bindings={
                9000: 9000
            }),
            environment={'MINIO_ACCESS_KEY': 'test',
                         'MINIO_SECRET_KEY': 'testforall'},
            command="server /data")
        self.docker.start(container=self.minio_container['Id'])

    def start_crawled_container(self):
        # start a container to be crawled
        self.docker.pull(repository='alpine', tag='latest')
        self.container = self.docker.create_container(
            image='alpine:latest', command='/bin/sleep 60')
        self.docker.start(container=self.container['Id'])

    def testFuntionalCosEmitter(self):
        env = os.environ.copy()
        mypath = os.path.dirname(os.path.realpath(__file__))

        # crawler itself needs to be root
        process = subprocess.Popen(
            [
                '/usr/bin/python', mypath + '/../../crawler/crawler.py',
                '--url', 'cos://127.0.0.1:9000',
                '--features', 'cpu,memory',
                '--crawlContainers', self.container['Id'],
                '--crawlmode', 'OUTCONTAINER',
                '--numprocesses', '1'
            ],
            env=env)
        stdout, stderr = process.communicate()
        assert process.returncode == 0        
        print stderr
        print stdout