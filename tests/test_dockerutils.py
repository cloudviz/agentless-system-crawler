from capturing import Capturing
import subprocess
import logging
import time
import sys
import simplejson as json

# sys.path.append('/home/kollerr/research/cloudsight-container/collector')
sys.path.append('../')

from crawler.dockerutils import (
    exec_dockerps, # wrapper
    _exec_dockerps, # fast version
    _exec_dockerps_slow, # slow version
    exec_docker_history,
    _exec_docker_history,
    _exec_docker_history_slow,
    exec_dockerinspect,
    _exec_dockerinspect,
    _exec_dockerinspect_slow,
)

#image = "d55e68e6cc9c"
image = "ubuntu"
image_id = None


def test_dockerps(long_id):
    found = False
    for inspect in exec_dockerps():
        c_long_id = inspect['Id']
        if long_id == c_long_id:
            found = True
    print sys._getframe().f_code.co_name, int(found)


def test_dockerps_fast(long_id):
    found = False
    for inspect in _exec_dockerps():
        c_long_id = inspect['Id']
        if long_id == c_long_id:
            found = True
    print sys._getframe().f_code.co_name, int(found)


def test_dockerps_slow(long_id):
    found = False
    for inspect in _exec_dockerps_slow():
        c_long_id = inspect['Id']
        if long_id == c_long_id:
            found = True
    print sys._getframe().f_code.co_name, int(found)


def test_docker_history(long_id):
    global image
    global image_id
    found = False
    history = exec_docker_history(long_id)
    found = image_id in history[0]['Id']
    print sys._getframe().f_code.co_name, int(found)


def test_docker_history_fast(long_id):
    global image
    global image_id
    found = False
    history = _exec_docker_history(long_id)
    found = image_id in history[0]['Id']
    print sys._getframe().f_code.co_name, int(found)


def test_docker_history_slow(long_id):
    global image
    global image_id
    found = False
    history = _exec_docker_history_slow(long_id)
    found = image_id in history[0]['Id']
    print sys._getframe().f_code.co_name, int(found)


def test_dockerinspect(long_id):
    global image
    found = False
    inspect_image = exec_dockerinspect(long_id)['Image']
    found = image_id in inspect_image
    print sys._getframe().f_code.co_name, int(found)

def test_dockerinspect_fast(long_id):
    global image
    found = False
    inspect_image = _exec_dockerinspect(long_id)['Image']
    found = image_id in inspect_image
    print sys._getframe().f_code.co_name, int(found)

def test_dockerinspect_slow(long_id):
    global image
    found = False
    inspect_image = _exec_dockerinspect_slow(long_id)['Image']
    found = image_id in inspect_image
    print sys._getframe().f_code.co_name, int(found)

if __name__ == '__main__':
    logging.basicConfig(
        filename='test_dockerutils.log',
        filemode='a',
        format='%(asctime)s %(levelname)s : %(message)s',
        level=logging.DEBUG)

    # start a container
    proc = subprocess.Popen(
        "docker run -d " + image + " sleep 60",
        shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    long_id = proc.stdout.read().strip()
    proc = subprocess.Popen(
        "docker inspect --format '{{.State.Pid}}' %s" % long_id,
        shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    pid = proc.stdout.read().split()[0]
    proc = subprocess.Popen(
        "docker inspect --format '{{.Id}}' %s" % image,
        shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    image_id = proc.stdout.read().strip()

    test_dockerps(long_id)
    test_dockerps_fast(long_id)
    test_dockerps_slow(long_id)
    test_docker_history(long_id)
    test_docker_history_fast(long_id)
    test_docker_history_slow(long_id)
    test_dockerinspect(long_id)
    test_dockerinspect_fast(long_id)
    test_dockerinspect_slow(long_id)

    # stop the container
    proc = subprocess.Popen(
        "docker rm -f %s" % long_id,
        shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    long_id = proc.stdout.read().strip()
