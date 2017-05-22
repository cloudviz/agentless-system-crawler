import logging
import mock
import os
import shutil
import sys
import time
import tempfile
import unittest

import docker
import requests.exceptions
from plugins.systems.fprobe_container_crawler import FprobeContainerCrawler
from utils.process_utils import start_child


# Tests the FprobeContainerCrawler class
# Throws an AssertionError if any test fails

FPROBE_FRAME = \
    '[{"data": "AAUACD6AE4dYsG5IAAGSWAAABngAAAAArBA3AqwQNwEAAAAAAAAAAAAAAAQAA'\
    'AFiPn/cGT5/3Bsfkez+ABsGAAAAAAAAAAAArBA3AawQNwIAAAAAAAAAAAAAAAYAAAHDPn/cF'\
    'j5/3BfcUh+QABsGAAAAAAAAAAAArBA3AgoKCgEAAAAAAAAAAAAAAAYAAAFiPn/dmj5//Q2TJ'\
    'gG7ABgGAAAAAAAAAAAArBA3AawQNwIAAAAAAAAAAAAAAAYAAAHDPn/cGT5/3BvcUx+QABsGA'\
    'AAAAAAAAAAArBA3AqwQNwEAAAAAAAAAAAAAAAQAAAFhPn/cGT5/3BsfkNxTABsGAAAAAAAAA'\
    'AAArBA3AawQNwIAAAAAAAAAAAAAAAYAAAG9Pn/cGT5/3Bvs/h+RABsGAAAAAAAAAAAArBA3A'\
    'qwQNwEAAAAAAAAAAAAAAAQAAAFhPn/cFj5/3BgfkNxSABsGAAAAAAAAAAAACgoKAawQNwIAA'\
    'AAAAAAAAAAAAAsAABn8Pn/dfj5//Q0Bu5MmABgGAAAAAAAAAAAA", "metadata": {"send'\
    'er": "127.0.0.1", "timestamp": 1487957576.000248, "ifname": "vethcfd6842'\
    '", "sport": 46246, "ip-addresses": ["172.16.55.2"], "container-id": "5f2'\
    'e9fb6168da249e1ef215c41c1454e921a7e4ee722d85191d3027703ea613e"}}]'


def simulate_socket_datacollector(params):
    """ simulate writing by the socket-datacollector """
    dir_idx = params.index('--dir')
    assert dir_idx > 0
    output_dir = params[dir_idx + 1]

    filepattern_idx = params.index('--filepattern')
    assert filepattern_idx > 0
    filepattern = params[filepattern_idx + 1]

    filename = os.path.join(output_dir, filepattern)
    with open(filename, 'w') as f:
        f.write(FPROBE_FRAME)
        print 'Write file %s' % filename
    with open(filename + ".tmp", 'w') as f:
        f.write(FPROBE_FRAME)


def mocked_start_child(params, pass_fds, null_fds, ign_sigs, setsid=False,
                       **kwargs):
    if params[0] == 'socket-datacollector':
        # in case the socket-datacollector is started, we just write
        # the frame without actually starting that program.
        simulate_socket_datacollector(params)

    # return appropriate values
    return start_child(['sleep', '1'], pass_fds, null_fds, ign_sigs, setsid)


def mocked_start_child_fprobe_fail(params, pass_fds, null_fds, ign_sigs,
                                   setsid=False, **kwargs):
    if params[0] == 'softflowd':
        return start_child(['___no_such_file'], pass_fds, null_fds, ign_sigs,
                           setsid, **kwargs)
    return start_child(['sleep', '1'], pass_fds, null_fds, ign_sigs, setsid,
                       **kwargs)


def mocked_start_child_collector_fail(params, pass_fds, null_fds, ign_sigs,
                                      setsid=False, **kwargs):
    if params[0] == 'socket-datacollector':
        return start_child(['___no_such_file'], pass_fds, null_fds, ign_sigs,
                           setsid, **kwargs)
    return start_child(['sleep', '1'], pass_fds, null_fds, ign_sigs,
                       setsid, **kwargs)


def mocked_psutil_process_iter():
    class MyProcess(object):
        def __init__(self, _name, _cmdline, _pid):
            self._name = _name
            self._cmdline = _cmdline
            self.pid = _pid

        def name(self):
            return self._name

        def cmdline(self):
            return self._cmdline
    yield MyProcess('softflowd', ['-i', 'test.eth0', '127.0.0.1:1234'], 11111)


# Tests conducted with a single container running.
class FprobeFunctionalTests(unittest.TestCase):
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
            image=self.image_name, command='ping -w 30 8.8.8.8')
        self.tempd = tempfile.mkdtemp(prefix='crawlertest.')
        self.docker.start(container=self.container['Id'])

        self.output_dir = os.path.join(self.tempd, 'crawler-fprobe')

        self.params = {
            'fprobe_user': 'nobody',
            'fprobe_output_dir': self.output_dir,
            'output_filepattern': 'testfile',
            'netflow_version': 10,
        }

        logging.basicConfig(stream=sys.stderr)
        self.logger = logging.getLogger("crawlutils").setLevel(logging.INFO)

    def tearDown(self):
        self.docker.stop(container=self.container['Id'])
        self.docker.remove_container(container=self.container['Id'])

        shutil.rmtree(self.tempd)

    @mock.patch('plugins.systems.fprobe_container_crawler.start_child',
                mocked_start_child)
    def test_crawl_outcontainer_fprobe(self):
        logger = logging.getLogger("crawlutils")
        logger.info('>>> Testcase: expecting collector output')

        fc = FprobeContainerCrawler()
        assert fc.get_feature() == 'fprobe'

        # the fake collector writes the single frame immediately
        res = []
        for data in fc.crawl(self.container['Id'], avoid_setns=False,
                             **self.params):
            res.append(data)
        assert len(res) == 1

    @mock.patch('plugins.systems.fprobe_container_crawler.start_child',
                mocked_start_child_fprobe_fail)
    def test_start_netflow_collection_fault1(self):
        logger = logging.getLogger("crawlutils")
        logger.info('>>> Testcase: fprobe fails to start')

        fc = FprobeContainerCrawler()
        assert fc.get_feature() == 'fprobe'

        # with fprobe failing to start, we won't get data
        res = []
        for data in fc.crawl(self.container['Id'], avoid_setns=False,
                             **self.params):
            res.append(data)
        assert len(res) == 0

    @mock.patch('plugins.systems.fprobe_container_crawler.start_child',
                mocked_start_child_collector_fail)
    def test_start_netflow_collection_fault2(self):
        logger = logging.getLogger("crawlutils")
        logger.info('>>> Testcase: collector fails to start')

        fc = FprobeContainerCrawler()
        assert fc.get_feature() == 'fprobe'

        # with fprobe failing to start, we won't get data
        res = []
        for data in fc.crawl(self.container['Id'], avoid_setns=False,
                             **self.params):
            res.append(data)
        assert len(res) == 0

    @mock.patch('plugins.systems.fprobe_container_crawler.start_child',
                mocked_start_child)
    def test_remove_datafiles(self):
        logger = logging.getLogger("crawlutils")
        logger.info('>>> Testcase: datafiles of disappeared interface '
                    'being removed')

        fc = FprobeContainerCrawler()
        assert fc.get_feature() == 'fprobe'

        # we pretend that an interface test.eth0 existed
        ifname = 'test.eth0'
        FprobeContainerCrawler.fprobes_started[ifname] = 1234

        self.params['output_filepattern'] = 'fprobe-{ifname}-{timestamp}'

        # create a datafile for this fake interface
        timestamp = int(time.time())
        filepattern = 'fprobe-{ifname}-{timestamp}'.format(ifname=ifname,
                                                           timestamp=timestamp)
        params = [
            'socket-datacollector',
            '--dir', self.output_dir,
            '--filepattern', filepattern,
        ]

        # have the fake socket-datacollector write a file with the ifname in
        # the filename
        fc.setup_outputdir(self.output_dir, os.getuid(), os.getgid())
        simulate_socket_datacollector(params)
        written_file = os.path.join(self.output_dir, filepattern)
        assert os.path.isfile(written_file)

        FprobeContainerCrawler.next_cleanup = 0
        # calling fc.crawl() will trigger a cleanup of that file
        # since our fake interface never existed
        fc.crawl(self.container['Id'], avoid_setns=False, **self.params)

        # file should be gone now
        assert not os.path.isfile(written_file)

    @mock.patch('plugins.systems.fprobe_container_crawler.psutil.process_iter',
                mocked_psutil_process_iter)
    def test_interfaces_with_fprobes(self):
        logger = logging.getLogger("crawlutils")
        logger.info('>>> Testcase: determine interfaces on which flow probes '
                    'are running')
        s = FprobeContainerCrawler.interfaces_with_fprobes()
        assert 'test.eth0' in s.keys()

    @mock.patch('plugins.systems.fprobe_container_crawler.start_child',
                mocked_start_child)
    def test_remove_stale_files(self):
        logger = logging.getLogger("crawlutils")
        logger.info('>>> Testcase: stale file being removed')

        fc = FprobeContainerCrawler()
        assert fc.get_feature() == 'fprobe'

        # we pretend that an interface test.eth0 existed
        ifname = 'test.eth0'
        FprobeContainerCrawler.fprobes_started[ifname] = 1234

        self.params['output_filepattern'] = 'fprobe-{ifname}-{timestamp}'

        # have the fake socket-datacollector write a file with the ifname in
        # the filename
        fc.setup_outputdir(self.output_dir, os.getuid(), os.getgid())

        written_file = os.path.join(self.output_dir, 'test.output')
        with open(written_file, 'a') as f:
            f.write('hello')

        assert os.path.isfile(written_file)

        # mock the stale file timeout so that our file will get removed
        # with in reasonable time
        FprobeContainerCrawler.STALE_FILE_TIMEOUT = 5

        # calling fc.crawl() will not trigger a cleanup of that file
        # the first time
        logger.info('1st crawl')
        fc.crawl(self.container['Id'], avoid_setns=False, **self.params)

        # file should still be here
        assert os.path.isfile(written_file)

        # the next time we will crawl, the file will be removed
        FprobeContainerCrawler.next_cleanup = time.time()
        time.sleep(FprobeContainerCrawler.STALE_FILE_TIMEOUT + 1)

        logger.info('2nd crawl')
        fc.crawl(self.container['Id'], avoid_setns=False, **self.params)

        # file should be gone now
        assert not os.path.isfile(written_file)

    if __name__ == '__main__':
        unittest.main()
