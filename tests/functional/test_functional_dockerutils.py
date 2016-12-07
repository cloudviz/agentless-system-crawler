import logging
import unittest
import docker
import requests.exceptions
import tempfile
import shutil

from utils.dockerutils import (
    exec_dockerps,
    exec_docker_history,
    exec_dockerinspect,
    _get_docker_server_version,
    get_docker_container_rootfs_path
)

# Tests conducted with a single container running.


class DockerUtilsTests(unittest.TestCase):
    image_name = 'alpine:latest'
    long_image_name = 'docker.io/alpine:latest'

    def setUp(self):
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

        self.docker.pull(repository='alpine', tag='latest')
        self.container = self.docker.create_container(
            image=self.image_name, command='/bin/sleep 60')
        self.tempd = tempfile.mkdtemp(prefix='crawlertest.')
        self.docker.start(container=self.container['Id'])

    def tearDown(self):
        self.docker.stop(container=self.container['Id'])
        self.docker.remove_container(container=self.container['Id'])

        shutil.rmtree(self.tempd)

    def test_docker_version(self):
        ver = _get_docker_server_version()
        import re
        pattern = re.compile("^[0-9]\.[0-9|\.]+$")
        assert pattern.match(ver)

    def test_dockerps(self):
        for inspect in exec_dockerps():
            c_long_id = inspect['Id']
            break  # there should only be one container anyway
        assert self.container['Id'] == c_long_id

    def test_docker_history(self):
        history = exec_docker_history(self.container['Id'])
        print history[0]
        assert self.image_name in history[0][
            'Tags'] or self.long_image_name in history[0]['Tags']

    def test_dockerinspect(self):
        inspect = exec_dockerinspect(self.container['Id'])
        print inspect
        assert self.container['Id'] == inspect['Id']

    def test_get_container_rootfs(self):
        root = get_docker_container_rootfs_path(self.container['Id'])
        print root
        assert root.startswith('/var/lib/docker')

    if __name__ == '__main__':
        logging.basicConfig(
            filename='test_dockerutils.log',
            filemode='a',
            format='%(asctime)s %(levelname)s : %(message)s',
            level=logging.DEBUG)

        unittest.main()
