import unittest
import docker
import requests.exceptions
import tempfile
import os
import shutil
import subprocess
import commands
import time
import multiprocessing
import semantic_version
from utils.dockerutils import _fix_version

# Tests conducted with a single container running.
# docker events supported avove docker version 1.8.0
VERSION_SPEC = semantic_version.Spec('>=1.8.1')


class CrawlerDockerEventTests(unittest.TestCase):

    def setUp(self):
        self.docker = docker.Client(
            base_url='unix://var/run/docker.sock', version='auto')
        try:
            if len(self.docker.containers()) != 0:
                raise Exception("Sorry, this test requires a machine with no "
                                "docker containers running.")
        except requests.exceptions.ConnectionError as e:
            print("Error connecting to docker daemon, are you in the docker "
                  "group? You need to be in the docker group.")

        self.docker.pull(repository='alpine', tag='latest')
        self.tempd = tempfile.mkdtemp(prefix='crawlertest-events.')

    def tearDown(self):
        containers = self.docker.containers()
        for container in containers:
            self.docker.stop(container=container['Id'])
            self.docker.remove_container(container=container['Id'])

        shutil.rmtree(self.tempd)
        # self.__exec_kill_crawlers()

    def __exec_crawler(self, cmd):
        status, output = commands.getstatusoutput(cmd)
        assert status == 0

    def __exec_create_container(self):
        container = self.docker.create_container(
            image='alpine:latest', command='/bin/sleep 60')
        self.docker.start(container=container['Id'])
        return container['Id']

    def __exec_delet_container(self, containerId):
        self.docker.stop(container=containerId)
        self.docker.remove_container(container=containerId)

    '''
    def __exec_kill_crawlers(self):
        procname = "python"
        for proc in psutil.process_iter():
            if proc.name() == procname:
                #cmdline = proc.cmdline()
                pid = proc.pid
                #if 'crawler.py' in cmdline[1]:
                os.kill(pid, signal.SIGTERM)
    '''

    '''
    This is a basic sanity test. It first creates a container and then starts
    crawler.  In this case, crawler would miss the create event, but it should
    be able to discover already running containers and snapshot them
    '''
    def testCrawlContainer0(self):
        env = os.environ.copy()
        mypath = os.path.dirname(os.path.realpath(__file__))
        os.makedirs(self.tempd + '/out')

        self.__exec_create_container()

        # crawler itself needs to be root
        process = subprocess.Popen(
            [
                '/usr/bin/python', mypath + '/../../crawler/crawler.py',
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

        with open(self.tempd + '/out/' + files[0], 'r') as f:
            output = f.read()
        assert 'interface-lo.if_octets.tx' in output
        assert 'cpu-0.cpu-idle' in output
        assert 'memory.memory-used' in output

        # clear the outut direcory
        shutil.rmtree(os.path.join(self.tempd, 'out'))

    '''
    In this test, crawler is started with high snapshot frequency (60 sec),
    and container is created immediately. Expected behaviour is that
    crawler should get interrupted and start snapshotting container immediately.

    '''
    def testCrawlContainer1(self):
        env = os.environ.copy()
        mypath = os.path.dirname(os.path.realpath(__file__))
        os.makedirs(self.tempd + '/out')

        # crawler itself needs to be root
        cmd = ''.join([
            '/usr/bin/python ', mypath + '/../../crawler/crawler.py ',
            '--url ', 'file://' + self.tempd + '/out/crawler ',
            '--features ', 'cpu,memory,interface ',
            '--crawlContainers ', 'ALL ',
            '--format ', 'graphite ',
            '--crawlmode ', 'OUTCONTAINER ',
            '--frequency ', '60 ',
            '--numprocesses ', '1 '
        ])

        crawlerProc = multiprocessing.Process(
            name='crawler', target=self.__exec_crawler,
            args=(cmd,))

        createContainerProc = multiprocessing.Process(
            name='createContainer', target=self.__exec_create_container
        )

        crawlerProc.start()
        createContainerProc.start()

        time.sleep(5)

        subprocess.call(['/bin/chmod', '-R', '777', self.tempd])

        files = os.listdir(self.tempd + '/out')
        assert len(files) == 1

        with open(self.tempd + '/out/' + files[0], 'r') as f:
            output = f.read()
        # print output  # only printed if the test fails
        assert 'interface-lo.if_octets.tx' in output
        assert 'cpu-0.cpu-idle' in output
        assert 'memory.memory-used' in output
        # clear the outut direcory
        shutil.rmtree(os.path.join(self.tempd, 'out'))
        crawlerProc.terminate()
        crawlerProc.join()

    '''
    In this test, crawler is started with shorter snapshot frequency (20 sec),
    and container is created immediately. Expected behaviour is that
    crawler should get intrupptted and start snapshotting container immediately.

    And then we will wait for crawler's next iteration to ensure, w/o docker event,
    crawler will timeout and snapshot container periodically
    '''
    def testCrawlContainer2(self):
        env = os.environ.copy()
        mypath = os.path.dirname(os.path.realpath(__file__))
        os.makedirs(self.tempd + '/out')

        # crawler itself needs to be root
        cmd = ''.join([
            '/usr/bin/python ', mypath + '/../../crawler/crawler.py ',
            '--url ', 'file://' + self.tempd + '/out/crawler ',
            '--features ', 'cpu,memory,interface ',
            '--crawlContainers ', 'ALL ',
            '--format ', 'graphite ',
            '--crawlmode ', 'OUTCONTAINER ',
            '--frequency ', '20 ',
            '--numprocesses ', '1 '
        ])

        crawlerProc = multiprocessing.Process(
            name='crawler', target=self.__exec_crawler,
            args=(cmd,))

        createContainerProc = multiprocessing.Process(
            name='createContainer', target=self.__exec_create_container
        )

        crawlerProc.start()
        createContainerProc.start()

        time.sleep(30)

        subprocess.call(['/bin/chmod', '-R', '777', self.tempd])

        files = os.listdir(self.tempd + '/out')
        docker_server_version = self.docker.version()['Version']
        if VERSION_SPEC.match(semantic_version.Version(_fix_version(docker_server_version))):
            assert len(files) == 2

        with open(self.tempd + '/out/' + files[0], 'r') as f:
            output = f.read()
        # print output  # only printed if the test fails
        assert 'interface-lo.if_octets.tx' in output
        assert 'cpu-0.cpu-idle' in output
        assert 'memory.memory-used' in output
        # clear the outut direcory
        shutil.rmtree(os.path.join(self.tempd, 'out'))
        crawlerProc.terminate()
        crawlerProc.join()


if __name__ == '__main__':
    unittest.main()
