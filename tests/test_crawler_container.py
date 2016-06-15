import unittest
import docker
import requests.exceptions
import tempfile
import os
import shutil
import subprocess

# Tests for crawlers in kraken crawlers configuration.


# Tests conducted with a single container running.
class SingleContainerTests(unittest.TestCase):

    def setUp(self):
        self.docker = docker.Client(base_url='unix://var/run/docker.sock', version='auto')
        try:
            if len(self.docker.containers()) != 0:
                raise Exception("Sorry, this test requires a machine with no docker containers running.")
        except requests.exceptions.ConnectionError as e:
            print "Error connecting to docker daemon, are you in the docker group? You need to be in the docker group."

        self.docker.pull(repository='alpine', tag='latest')
        self.container = self.docker.create_container(image='alpine:latest', command='/bin/sleep 60')
        self.tempd = tempfile.mkdtemp(prefix='crawlertest.')
        self.docker.start(container=self.container['Id'])

    def tearDown(self):
        self.docker.stop(container=self.container['Id'])
        self.docker.remove_container(container=self.container['Id'])

        shutil.rmtree(self.tempd)

    def testCrawlContainer(self):
        env = os.environ.copy()
        mypath = os.path.dirname(os.path.realpath(__file__))
        os.makedirs(self.tempd + '/out')

        #crawler itself needs to be root
        process = subprocess.Popen(
            [
                '/usr/bin/python2.7', mypath + '/../crawler/crawler.py',
                '--url', 'file://' + self.tempd + '/out/crawler',
                '--features', 'cpu,memory,interface',
                '--crawlContainers', 'ALL',
                '--format', 'graphite',
                '--crawlmode', 'OUTCONTAINER',
                '--numprocesses', '1'
            ],
            env=env)
        stdout, stderr = process.communicate()
        assert process.returncode == 0

        subprocess.call(['/bin/chmod', '-R', '777', self.tempd])

        files = os.listdir(self.tempd + '/out')
        assert len(files) == 1

        f = open(self.tempd + '/out/' + files[0], 'r')
        output = f.read()
        print output # only printed if the test fails
        assert 'interface-lo.if_octets.tx' in output
        assert 'cpu-0.cpu-idle' in output
        assert 'memory.memory-used' in output
        f.close()

if __name__ == '__main__':
    unittest.main()
