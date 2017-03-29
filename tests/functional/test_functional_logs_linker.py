import unittest
import docker
import os
import shutil
import sys
import subprocess
import plugins_manager

from containers_logs_linker import DockerContainersLogsLinker
from worker import Worker
from dockercontainer import HOST_LOG_BASEDIR
from utils.misc import get_host_ipaddr

import logging


class LogsLinkerTests(unittest.TestCase):

    def setUp(self):
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        root.addHandler(ch)
        plugins_manager.runtime_env = None
        self.container = {}
        self.container_name = 'LogLinkerContainer'
        self.host_namespace = get_host_ipaddr()
        try:
            shutil.rmtree(os.path.join(HOST_LOG_BASEDIR, self.host_namespace,
                                       self.container_name))
        except OSError:
            pass

    def startContainer(self):
        self.docker = docker.Client(
            base_url='unix://var/run/docker.sock', version='auto')
        self.docker.pull(repository='ubuntu', tag='latest')
        self.container = self.docker.create_container(
            image='ubuntu:latest',
            command='bash -c "echo hi ; echo hi > /var/log/messages; /bin/sleep 120"',
            name=self.container_name)
        self.docker.start(container=self.container['Id'])

    def tearDown(self):
        try:
            self.removeContainer()
            shutil.rmtree(os.path.join(HOST_LOG_BASEDIR, self.host_namespace,
                                       self.container_name))
        except Exception:
            pass

    def removeContainer(self):
        self.docker.stop(container=self.container['Id'])
        self.docker.remove_container(container=self.container['Id'])

    def testLinkUnlinkContainer(self):
        docker_log = os.path.join(HOST_LOG_BASEDIR, self.host_namespace,
                                  self.container_name, 'docker.log')
        messages_log = os.path.join(HOST_LOG_BASEDIR, self.host_namespace,
                                    self.container_name, 'var/log/messages')
        crawler = DockerContainersLogsLinker(
            environment='cloudsight',
            user_list='ALL',
            host_namespace=self.host_namespace)
        worker = Worker(crawler=crawler)

        self.startContainer()
        worker.iterate()
        with open(docker_log, 'r') as log:
            assert 'hi' in log.read()
        with open(messages_log, 'r') as log:
            assert 'hi' in log.read()
        assert os.path.exists(docker_log)
        assert os.path.exists(messages_log)
        assert os.path.islink(docker_log)
        assert os.path.islink(messages_log)

        self.removeContainer()
        worker.iterate()
        assert not os.path.exists(docker_log)
        assert not os.path.exists(messages_log)
        assert not os.path.islink(docker_log)
        assert not os.path.islink(messages_log)

        self.startContainer()
        worker.iterate()
        assert os.path.exists(docker_log)
        with open(docker_log, 'r') as log:
            assert 'hi' in log.read()
        with open(messages_log, 'r') as log:
            assert 'hi' in log.read()
        assert os.path.exists(messages_log)
        assert os.path.islink(docker_log)
        assert os.path.islink(messages_log)

        self.removeContainer()

    def testLinkUnlinkContainerCli(self):
        docker_log = os.path.join(HOST_LOG_BASEDIR, self.host_namespace,
                                  self.container_name, 'docker.log')
        messages_log = os.path.join(HOST_LOG_BASEDIR, self.host_namespace,
                                    self.container_name, 'var/log/messages')

        self.startContainer()

        # crawler itself needs to be root
        env = os.environ.copy()
        mypath = os.path.dirname(os.path.realpath(__file__))
        process = subprocess.Popen(
            [
                '/usr/bin/python', mypath + '/../../crawler/containers_logs_linker.py'
            ],
            env=env)
        stdout, stderr = process.communicate()
        assert process.returncode == 0

        print stderr
        print stdout

        with open(docker_log, 'r') as log:
            assert 'hi' in log.read()
        with open(messages_log, 'r') as log:
            assert 'hi' in log.read()
        assert os.path.exists(docker_log)
        assert os.path.exists(messages_log)
        assert os.path.islink(docker_log)
        assert os.path.islink(messages_log)

        self.removeContainer()


if __name__ == '__main__':
    unittest.main()
