import docker
import logging
import requests.exceptions
# import os
import shutil
# import subprocess
import sys
import tempfile
import unittest

from crawler.namespace import run_as_another_namespace
from crawler.crawler_exceptions import CrawlTimeoutError  # , CrawlError

all_namespaces = ["user", "pid", "uts", "ipc", "net", "mnt"]


# Functions used to test the library
def func(arg1=None, arg2=None):
    return "test %s %s" % (arg1, arg2)


def func_no_args(arg="default"):
    return "test %s" % (arg)


class FooError(Exception):
    pass


def func_crash(arg):
    raise FooError("oops")


def func_infinite_loop(arg):
    while True:
        a = 1  # noqa

# Tests conducted with a single container running.


class NamespaceLibTests(unittest.TestCase):
    image_name = 'alpine:latest'

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
        self.container = self.docker.create_container(
            image=self.image_name, command='/bin/sleep 60')
        self.tempd = tempfile.mkdtemp(prefix='crawlertest.')
        self.docker.start(container=self.container['Id'])
        inspect = self.docker.inspect_container(self.container['Id'])
        print(inspect)
        self.pid = str(inspect['State']['Pid'])

    def tearDown(self):
        self.docker.stop(container=self.container['Id'])
        self.docker.remove_container(container=self.container['Id'])

        shutil.rmtree(self.tempd)

    def test_run_as_another_namespace_simple_function(self):
        res = run_as_another_namespace(
            self.pid, all_namespaces, func, "arg1", "arg2")
        assert res == "test arg1 arg2"
        print(sys._getframe().f_code.co_name, 1)

    def test_run_as_another_namespace_simple_function_no_args(self):
        res = run_as_another_namespace(self.pid, all_namespaces, func_no_args)
        assert res == "test default"
        print(sys._getframe().f_code.co_name, 1)

    def test_run_as_another_namespace_crashing_function(self):
        try:
            res = run_as_another_namespace(
                self.pid, all_namespaces, func_crash, "arg")
        except FooError as e:
            # we shuld get a FooError exception
            pass  # all good
        except Exception as e:
            assert False

    # TODO: why it fails here and not at old/test_namespace.py?
    def _test_run_as_another_namespace_infinite_loop_function(self):
        try:
            res = run_as_another_namespace(
                self.pid, all_namespaces, func_infinite_loop, "arg")
        except CrawlTimeoutError as e:
            # we should get a TimeoutError exception
            pass  # all good
        except Exception as e:
            assert False

    if __name__ == '__main__':
        logging.basicConfig(filename='test_namespace.log', filemode='a',
                            format='%(asctime)s %(levelname)s : %(message)s',
                            level=logging.DEBUG)

        unittest.main()
