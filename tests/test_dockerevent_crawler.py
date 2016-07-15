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
# Tests conducted with a single container running.

class CrawlerDockerEventTests(unittest.TestCase):

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
        self.tempd = tempfile.mkdtemp(prefix='crawlertest-events.')

    def tearDown(self):
	containers = self.docker.containers()
	for container in containers:
            self.docker.stop(container=container['Id'])
            self.docker.remove_container(container=container['Id'])

        #shutil.rmtree(self.tempd)

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
    This is a basic sanity test. It first creates a container and then starts crawler.
    In this case, crawler would miss the create event, but it should be able to
    discover already running containers and snapshot them
    '''
    def testCrawlContainer0(self):
        env = os.environ.copy()
        mypath = os.path.dirname(os.path.realpath(__file__))
        os.makedirs(self.tempd + '/out')

	self.__exec_create_container()

        # crawler itself needs to be root
        process = subprocess.Popen(
            [
                '/usr/bin/python', mypath + '/../crawler/crawler.py',
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
        assert 'interface-lo.if_octets.tx' in output
        assert 'cpu-0.cpu-idle' in output
        assert 'memory.memory-used' in output
        f.close()

	#clear the outut direcory
	shutil.rmtree(os.path.join(self.tempd, 'out')) 
  	
    '''
    In this test, crawler is started with high snapshot frequency (60 sec),
    and container is created immediately. Expected behaviour is that
    crawler should get intrupptted and start snapshotting container immediately.

    And then we will wait for crawler's next iteration to ensure, w/o docker event,
    crawler will timeout and snapshot container periodically
    '''
    def testCrawlContainer1(self):
        env = os.environ.copy()
        mypath = os.path.dirname(os.path.realpath(__file__))
        os.makedirs(self.tempd + '/out')
        
	# crawler itself needs to be root
	cmd = ''.join([
                '/usr/bin/python ', mypath + '/../crawler/crawler.py ',
                '--url ', 'file://' + self.tempd + '/out/crawler ',
                '--features ', 'cpu,memory,interface ',
                '--crawlContainers ', 'ALL ',
                '--format ', 'graphite ',
                '--crawlmode ', 'OUTCONTAINER ',
                '--numprocesses ', '4 '
            ])
	crawlerProc = multiprocessing.Process(
			name='crawler', target=self.__exec_crawler,
			args=(cmd,))
	
	createContainerProc = multiprocessing.Process(
                        name='createContainer', target=self.__exec_create_container
                )

	crawlerProc.start()
	createContainerProc.start()

	while True:
		if crawlerProc.is_alive():
			time.sleep(0.1)
		else:
			break		
	
        subprocess.call(['/bin/chmod', '-R', '777', self.tempd])

        files = os.listdir(self.tempd + '/out')
        assert len(files) == 1

        f = open(self.tempd + '/out/' + files[0], 'r')
        output = f.read()
        #print output  # only printed if the test fails
        assert 'interface-lo.if_octets.tx' in output
        assert 'cpu-0.cpu-idle' in output
        assert 'memory.memory-used' in output
        f.close()

if __name__ == '__main__':
    unittest.main()
