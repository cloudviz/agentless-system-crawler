import json
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
from plugins.systems.ctprobe_container_crawler import CTProbeContainerCrawler
from utils.process_utils import start_child


# Tests the FprobeContainerCrawler class
# Throws an AssertionError if any test fails

CTPROBE_FRAME = \
    '[{"data":"xAAAAAABAAYAAAAAAAAAAAIAAAA0AAGAFAABgAgAAQCsEQABCAACAKwRAA4cA' \
    'AKABQABAAYAAAAGAAIAiEYAAAYAAwARWwAANAACgBQAAYAIAAEArBEADggAAgCsEQABHAAC' \
    'gAUAAQAGAAAABgACABFbAAAGAAMAiEYAAAgADADhBU3ACAADAAAAAYgIAAcAAAAAeDAABIA' \
    'sAAGABQABAAEAAAAFAAIABwAAAAUAAwAAAAAABgAEAAMAAAAGAAUAAAAAAA==","metadat' \
    'a":{"ip-addresses":["172.17.0.14"]}},{"data":"jAAAAAIBAAAAAAAAAAAAAAIAA' \
    'AA0AAGAFAABgAgAAQCsEQABCAACAKwRAA4cAAKABQABAAYAAAAGAAIAiDYAAAYAAwARWwAA' \
    'NAACgBQAAYAIAAEArBEADggAAgCsEQABHAACgAUAAQAGAAAABgACABFbAAAGAAMAiDYAAAg' \
    'ADAAM3QUACAADAAAAAY4=","metadata":{"ip-addresses":["172.17.0.14"]}}]'


def simulate_ctprobe(url):
    """ simulate writing by ctprobe """
    filename = url.split('://')[1]
    with open(filename, 'w') as f:
        f.write(CTPROBE_FRAME)
    with open(filename + ".tmp", 'w') as f:
        f.write(CTPROBE_FRAME)


def mocked_add_collector(self, url, ipaddresses, ifname):
    code, content = self.send_request('add_collector',
                                      [url, ipaddresses, ifname])
    if code == 200:
        # in this case we simulate a file being written...
        simulate_ctprobe(url)
        return True
    else:
        raise Exception('HTTP Error %d: %s' % (code, content['error']))


def mocked_start_child(params, pass_fds, null_fds, ign_sigs, setsid=False,
                       **kwargs):
    return start_child(['sleep', '1'], pass_fds, null_fds, ign_sigs, setsid)


def mocked_start_child_ctprobe_except(params, pass_fds, null_fds, ign_sigs,
                                      setsid=False, **kwargs):
    if params[0] == 'conntrackprobe':
        raise Exception('Refusing to start %s' % params[0])


def mocked_session_get(self, path, data=''):
    class Session(object):
        def __init__(self, status_code, content):
            self.status_code = status_code
            self.content = json.dumps(content)

    return Session(200, {'error': ''})


def mocked_session_get_fail(self, path, data=''):
    class Session(object):
        def __init__(self, status_code, content):
            self.status_code = status_code
            self.content = json.dumps(content)

    return Session(400, {'error': 'Bad request'})


def mocked_ethtool_get_peer_ifindex(ifname):
    raise Exception('ethtool exception')


def mocked_check_ctprobe_alive(self, pid):
    return True


# Tests conducted with a single container running.
class CtprobeFunctionalTests(unittest.TestCase):
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

        self.output_dir = os.path.join(self.tempd, 'crawler-ctprobe')

        self.params = {
            'ctprobe_user': 'nobody',
            'ctprobe_output_dir': self.output_dir,
            'output_filepattern': 'testfile',
        }

        logging.basicConfig(stream=sys.stderr)
        self.logger = logging.getLogger("crawlutils").setLevel(logging.INFO)

    def tearDown(self):
        self.docker.stop(container=self.container['Id'])
        self.docker.remove_container(container=self.container['Id'])

        shutil.rmtree(self.tempd)
        CTProbeContainerCrawler.ctprobe_pid = 0
        CTProbeContainerCrawler.ifaces_monitored = []

    @mock.patch('plugins.systems.ctprobe_container_crawler.start_child',
                mocked_start_child)
    @mock.patch('plugins.systems.ctprobe_container_crawler.'
                'requests_unixsocket.Session.get', mocked_session_get)
    @mock.patch('plugins.systems.ctprobe_container_crawler.'
                'ConntrackProbeClient.add_collector', mocked_add_collector)
    def test_crawl_outcontainer_ctprobe(self):
        logger = logging.getLogger("crawlutils")
        logger.info('>>> Testcase: expecting collector output')

        num = len(CTProbeContainerCrawler.ifaces_monitored)

        ctc = CTProbeContainerCrawler()
        assert ctc.get_feature() == 'ctprobe'

        # the fake collector writes the single frame immediately
        res = []
        for data in ctc.crawl(self.container['Id'], avoid_setns=False,
                              **self.params):
            res.append(data)
        assert len(res) == 1
        assert len(CTProbeContainerCrawler.ifaces_monitored) == num + 1

    @mock.patch('plugins.systems.ctprobe_container_crawler.start_child',
                mocked_start_child)
    @mock.patch('plugins.systems.ctprobe_container_crawler.'
                'requests_unixsocket.Session.get', mocked_session_get_fail)
    def test_start_netlink_collection_fault1(self):
        logger = logging.getLogger("crawlutils")
        logger.info('>>> Testcase: collector cannot be configured')

        ctc = CTProbeContainerCrawler()
        assert ctc.get_feature() == 'ctprobe'

        # with ctprobe failing to start, we won't get data
        res = []
        for data in ctc.crawl(self.container['Id'], avoid_setns=False,
                              **self.params):
            res.append(data)
        assert len(res) == 0
        assert len(CTProbeContainerCrawler.ifaces_monitored) == 0

    @mock.patch('plugins.systems.ctprobe_container_crawler.start_child',
                mocked_start_child)
    @mock.patch('plugins.systems.ctprobe_container_crawler.'
                'requests_unixsocket.Session.get', mocked_session_get)
    @mock.patch('plugins.systems.ctprobe_container_crawler.'
                'ConntrackProbeClient.add_collector', mocked_add_collector)
    def test_start_netlink_collection_fault4(self):
        logger = logging.getLogger("crawlutils")
        logger.info('>>> Testcase: collector cannot be configured')

        ctprobe_user = self.params['ctprobe_user']
        self.params['ctprobe_user'] = 'user-does-not-exist'

        ctc = CTProbeContainerCrawler()
        assert ctc.get_feature() == 'ctprobe'

        # with ctprobe failing to start, we won't get data
        assert not ctc.crawl(self.container['Id'], avoid_setns=False,
                             **self.params)
        assert len(CTProbeContainerCrawler.ifaces_monitored) == 0

        self.params['ctprobe_user'] = ctprobe_user

    @mock.patch('plugins.systems.ctprobe_container_crawler.start_child',
                mocked_start_child_ctprobe_except)
    @mock.patch('plugins.systems.ctprobe_container_crawler.'
                'requests_unixsocket.Session.get', mocked_session_get)
    @mock.patch('plugins.systems.ctprobe_container_crawler.'
                'ConntrackProbeClient.add_collector', mocked_add_collector)
    def test_start_netlink_collection_fault5(self):
        logger = logging.getLogger("crawlutils")
        logger.info('>>> Testcase: conntrackprobe fails to start')

        ctc = CTProbeContainerCrawler()
        assert ctc.get_feature() == 'ctprobe'

        assert not ctc.crawl(self.container['Id'], avoid_setns=False,
                             **self.params)
        assert len(CTProbeContainerCrawler.ifaces_monitored) == 0

        assert not ctc.check_ctprobe_alive(CTProbeContainerCrawler.ctprobe_pid)
        # this should always fail
        assert not ctc.check_ctprobe_alive(1)

    @mock.patch('plugins.systems.ctprobe_container_crawler.start_child',
                mocked_start_child)
    @mock.patch('plugins.systems.ctprobe_container_crawler.'
                'requests_unixsocket.Session.get', mocked_session_get)
    @mock.patch('plugins.systems.ctprobe_container_crawler.'
                'ethtool_get_peer_ifindex', mocked_ethtool_get_peer_ifindex)
    def test_start_netlink_collection_fault6(self):
        logger = logging.getLogger("crawlutils")
        logger.info('>>> Testcase: ethtool throws an error')

        ctc = CTProbeContainerCrawler()
        assert ctc.get_feature() == 'ctprobe'

        # with ctprobe failing to start, we won't get data
        res = []
        for data in ctc.crawl(self.container['Id'], avoid_setns=False,
                              **self.params):
            res.append(data)
        assert len(res) == 0
        assert len(CTProbeContainerCrawler.ifaces_monitored) == 0

    @mock.patch('plugins.systems.ctprobe_container_crawler.start_child',
                mocked_start_child)
    @mock.patch('plugins.systems.ctprobe_container_crawler.'
                'requests_unixsocket.Session.get', mocked_session_get)
    @mock.patch('plugins.systems.ctprobe_container_crawler.'
                'ConntrackProbeClient.add_collector', mocked_add_collector)
    @mock.patch('plugins.systems.ctprobe_container_crawler.'
                'CTProbeContainerCrawler.check_ctprobe_alive',
                mocked_check_ctprobe_alive)
    def test_remove_datafiles(self):
        logger = logging.getLogger("crawlutils")
        logger.info('>>> Testcase: datafiles of disappeared interface '
                    'being removed')

        ctc = CTProbeContainerCrawler()
        assert ctc.get_feature() == 'ctprobe'

        # we pretend that an interface test.eth0 existed
        ifname = 'test.eth0'
        CTProbeContainerCrawler.ifaces_monitored.append(ifname)

        self.params['output_filepattern'] = 'ctprobe-{ifname}-{timestamp}'

        # create a datafile for this fake interface
        timestamp = int(time.time())
        filepattern = 'ctprobe-{ifname}-{timestamp}' \
                      .format(ifname=ifname, timestamp=timestamp)
        # have the ctprobe write a file with the ifname in
        # the filename
        ctc.setup_outputdir(self.output_dir, os.getuid(), os.getgid())
        simulate_ctprobe('file+json://%s/%s' % (self.output_dir, filepattern))
        written_file = os.path.join(self.output_dir, filepattern)
        assert os.path.isfile(written_file)

        CTProbeContainerCrawler.next_cleanup = 0
        # calling ctc.crawl() will trigger a cleanup of that file
        # since our fake interface never existed
        ctc.crawl(self.container['Id'], avoid_setns=False, **self.params)

        # file should be gone now
        assert not os.path.isfile(written_file)

    @mock.patch('plugins.systems.ctprobe_container_crawler.start_child',
                mocked_start_child)
    @mock.patch('plugins.systems.ctprobe_container_crawler.'
                'requests_unixsocket.Session.get', mocked_session_get)
    def test_remove_stale_files(self):
        logger = logging.getLogger("crawlutils")
        logger.info('>>> Testcase: stale file being removed')

        ctc = CTProbeContainerCrawler()
        assert ctc.get_feature() == 'ctprobe'

        # we pretend that an interface test.eth0 existed
        ifname = 'test.eth0'
        CTProbeContainerCrawler.ifaces_monitored.append(ifname)

        self.params['output_filepattern'] = 'ctprobe-{ifname}-{timestamp}'

        # have the fake socket-datacollector write a file with the ifname in
        # the filename
        ctc.setup_outputdir(self.output_dir, os.getuid(), os.getgid())

        written_file = os.path.join(self.output_dir, 'test.output')
        with open(written_file, 'a') as f:
            f.write('hello')

        assert os.path.isfile(written_file)

        # mock the stale file timeout so that our file will get removed
        # with in reasonable time
        CTProbeContainerCrawler.STALE_FILE_TIMEOUT = 5

        # calling ctc.crawl() will not trigger a cleanup of that file
        # the first time
        logger.info('1st crawl')
        ctc.crawl(self.container['Id'], avoid_setns=False, **self.params)

        # file should still be here
        assert os.path.isfile(written_file)

        # the next time we will crawl, the file will be removed
        CTProbeContainerCrawler.next_cleanup = time.time()
        time.sleep(CTProbeContainerCrawler.STALE_FILE_TIMEOUT + 1)

        logger.info('2nd crawl')
        ctc.crawl(self.container['Id'], avoid_setns=False, **self.params)

        # file should be gone now
        assert not os.path.isfile(written_file)

    if __name__ == '__main__':
        unittest.main()
