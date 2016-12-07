import logging
import shutil
import sys
import tempfile
import time
import unittest

import docker
import requests.exceptions

from utils.crawler_exceptions import CrawlTimeoutError
from utils.namespace import run_as_another_namespace

all_namespaces = ["user", "pid", "uts", "ipc", "net", "mnt"]


# Functions used to test the library
def func_args(arg1, arg2):
    return "test %s %s" % (arg1, arg2)

def func_kwargs(arg1='a', arg2='b'):
    return "test %s %s" % (arg1, arg2)

def func_mixed_args(arg1, arg2='b'):
    return "test %s %s" % (arg1, arg2)

def func_no_args(arg="default"):
    return "test %s" % (arg)


class FooError(Exception):
    pass


def func_crash(arg, *args, **kwargs):
    print locals()
    raise FooError("oops")


def func_infinite_loop(arg):
    while True:
        time.sleep(1)

# Tests conducted with a single container running.


class NamespaceLibTests(unittest.TestCase):
    image_name = 'alpine:latest'

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
            image=self.image_name, command='/bin/sleep 300')
        self.tempd = tempfile.mkdtemp(prefix='crawlertest.')
        self.docker.start(container=self.container['Id'])
        inspect = self.docker.inspect_container(self.container['Id'])
        print inspect
        self.pid = str(inspect['State']['Pid'])

    def tearDown(self):
        self.docker.stop(container=self.container['Id'])
        self.docker.remove_container(container=self.container['Id'])

        shutil.rmtree(self.tempd)

    def test_run_as_another_namespace_function_args(self):
        res = run_as_another_namespace(
            self.pid, all_namespaces, func_args, "arg1", "arg2")
        assert res == "test arg1 arg2"
        print sys._getframe().f_code.co_name, 1

    def test_run_as_another_namespace_function_kwargs(self):
        res = run_as_another_namespace(
            self.pid, all_namespaces, func_kwargs, arg1="arg1", arg2="arg2")
        assert res == "test arg1 arg2"
        print sys._getframe().f_code.co_name, 1

    def test_run_as_another_namespace_function_mixed_args(self):
        res = run_as_another_namespace(
            self.pid, all_namespaces, func_mixed_args, "arg1", arg2="arg2")
        assert res == "test arg1 arg2"
        print sys._getframe().f_code.co_name, 1

    def test_run_as_another_namespace_simple_function_no_args(self):
        res = run_as_another_namespace(self.pid, all_namespaces, func_no_args)
        assert res == "test default"
        print sys._getframe().f_code.co_name, 1

    def test_run_as_another_namespace_crashing_function(self):
        with self.assertRaises(FooError):
            run_as_another_namespace(
                self.pid, all_namespaces, func_crash, "arg")

    def test_run_as_another_namespace_infinite_loop_function(self):
        with self.assertRaises(CrawlTimeoutError):
            run_as_another_namespace(
                self.pid, all_namespaces, func_infinite_loop, "arg")

    if __name__ == '__main__':
        logging.basicConfig(
            filename='test_namespace.log',
            filemode='a',
            format='%(asctime)s %(levelname)s : %(message)s',
            level=logging.DEBUG)

        unittest.main()
