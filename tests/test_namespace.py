from capturing import Capturing
import sys
import logging
import subprocess

sys.path.append('../')

from config_and_metrics_crawler.namespace import run_as_another_namespace
from config_and_metrics_crawler.crawler_exceptions import CrawlTimeoutError, CrawlError

all_namespaces = ["user", "pid", "uts", "ipc", "net", "mnt"]

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
        a = 1

def test_run_as_another_namespace_simple_function(pid):
    res = run_as_another_namespace(pid, all_namespaces, func, "argumento1", "argumento2")
    assert res == "test argumento1 argumento2"
    print sys._getframe().f_code.co_name, 1

def test_run_as_another_namespace_simple_function_no_args(pid):
    res = run_as_another_namespace(pid, all_namespaces, func_no_args)
    assert res == "test default"
    print sys._getframe().f_code.co_name, 1
    

def test_run_as_another_namespace_crashing_function(pid):
    try:
        res = run_as_another_namespace(pid, all_namespaces, func_crash, "argumento")
    except FooError, e:
        print sys._getframe().f_code.co_name, 1
        return
    except Exception, e:
        print sys._getframe().f_code.co_name, 0


def test_run_as_another_namespace_infinite_loop_function(pid):
    try:
        res = run_as_another_namespace(pid, all_namespaces, func_infinite_loop, "argumento")
    except CrawlTimeoutError, e:
        # we should get a timeout error
        print sys._getframe().f_code.co_name, 1
    except Exception, e:
        print sys._getframe().f_code.co_name, 0


if __name__ == '__main__':
    logging.basicConfig(filename='test_namespace.log', filemode='a', format='%(asctime)s %(levelname)s : %(message)s', level=logging.DEBUG)

    # start a container
    proc = subprocess.Popen(
            "docker run -d ubuntu sleep 300",
            shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    long_id = proc.stdout.read().strip()
    proc = subprocess.Popen(                                                  
            "docker inspect --format '{{.State.Pid}}' %s" % long_id,
            shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    pid = proc.stdout.read().split()[0]


    # run tests
    test_run_as_another_namespace_simple_function(pid)
    test_run_as_another_namespace_simple_function_no_args(pid)
    test_run_as_another_namespace_crashing_function(pid)
    test_run_as_another_namespace_simple_function(pid)
    test_run_as_another_namespace_infinite_loop_function(pid)
    test_run_as_another_namespace_simple_function(pid)
    test_run_as_another_namespace_infinite_loop_function(pid)
    test_run_as_another_namespace_simple_function(pid)


    # stop the container
    proc = subprocess.Popen(
            "docker rm -f %s" % long_id,
            shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    long_id = proc.stdout.read().strip()
