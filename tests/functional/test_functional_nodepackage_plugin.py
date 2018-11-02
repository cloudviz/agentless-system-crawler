import unittest
import docker
import requests.exceptions
from plugins.systems.nodepackage_container_crawler import NodePackageCrawler


# Tests conducted with a single container running.
class NodePackagePluginFunctionalTests(unittest.TestCase):
    image_name = 'node:11.0'

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

        self.docker.pull(repository='node', tag='11.0')
        self.container = self.docker.create_container(
            image=self.image_name, command='sleep 60')
        self.docker.start(container=self.container['Id'])

    def tearDown(self):
        self.docker.stop(container=self.container['Id'])
        self.docker.remove_container(container=self.container['Id'])

    def test_crawl_outcontainer_node(self):
        fc = NodePackageCrawler()
        output = list(fc.crawl(self.container['Id']))
        num_packages = len(output)
        assert num_packages > 0
        output = "%s" % output
        assert 'npm' in output

    if __name__ == '__main__':
        unittest.main()
