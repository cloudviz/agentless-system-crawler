import mock
import unittest

from crawler.containers import (list_all_containers,
                                get_filtered_list_of_containers)


def mocked_exists(pid):
    return True


class DockerContainer():

    def __init__(self, pid):
        self.pid = pid
        self.short_id = pid
        self.long_id = pid
        self.process_namespace = pid

    def __str__(self):
        return 'container %s' % self.pid

    def is_docker_container(self):
        return True

DOCKER_IDS = ['101', '102', '103', '104', '105', '106']


def mocked_list_docker_containers(container_opts={}, user_list='ALL'):
    for long_id in DOCKER_IDS:

        if user_list not in ['ALL', 'all', 'All']:
            user_ctrs = [cid[:12] for cid in user_list.split(',')]
            short_id = long_id[:12]
            if short_id not in user_ctrs:
                continue

        c = DockerContainer(long_id)
        yield c


class PsUtilProcess():

    def __init__(self, pid):
        self.pid = pid


class ContainersTests(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    @mock.patch('crawler.containers.list_docker_containers',
                side_effect=lambda container_opts, user_list='ALL':
                mocked_list_docker_containers(container_opts, user_list))
    @mock.patch('crawler.containers.container.namespace.get_pid_namespace',
                side_effect=lambda pid: pid)
    @mock.patch('crawler.containers.container.psutil.process_iter',
                side_effect=lambda: [PsUtilProcess('4'),  # container
                                     PsUtilProcess('1'),  # init
                                     PsUtilProcess('5')])  # crawler
    @mock.patch('crawler.containers.container.misc.process_is_crawler',
                side_effect=lambda pid: True if pid == '5' else False)
    def test_list_all_containers(self, *args):
        pids = [c.pid for c in list_all_containers()]
        # pid 1 is the init process, which is not a container
        # according to the definition in container.py
        assert set(pids) == set(DOCKER_IDS + ['4'])
        assert '1' not in pids  # init process
        assert '5' not in pids  # crawler process
        assert args[0].call_count == 2
        assert args[1].call_count == 1
        assert args[2].call_count == 3
        assert args[3].call_count == 1

    @mock.patch('crawler.containers.list_docker_containers',
                side_effect=lambda container_opts, user_list='ALL':
                mocked_list_docker_containers(container_opts, user_list))
    @mock.patch('crawler.containers.container.namespace.get_pid_namespace',
                side_effect=lambda pid: pid)
    @mock.patch('crawler.containers.container.psutil.process_iter',
                side_effect=lambda: [PsUtilProcess('4'),  # container
                                     PsUtilProcess('1'),  # init
                                     PsUtilProcess('5')])  # crawler
    @mock.patch('crawler.containers.container.misc.process_is_crawler',
                side_effect=lambda pid: True if pid == '5' else False)
    def test_list_all_containers_input_list(self, *args):
        pids = [c.pid for c in list_all_containers(user_list='102')]
        # pid 1 is the init process, which is not a container
        # according to the definition in container.py
        assert set(pids) == set(['102'])
        assert '3' not in pids  # filtered container
        assert '4' not in pids  # filtered container
        assert '1' not in pids  # init process
        assert '5' not in pids  # crawler process

    @mock.patch('crawler.containers.list_docker_containers',
                side_effect=lambda container_opts, user_list='ALL':
                mocked_list_docker_containers(container_opts, user_list))
    @mock.patch('crawler.containers.container.namespace.get_pid_namespace',
                side_effect=lambda pid: pid)
    @mock.patch('crawler.containers.container.psutil.process_iter',
                side_effect=lambda: [PsUtilProcess('4'),  # container
                                     PsUtilProcess('1'),  # init
                                     PsUtilProcess('5')])  # crawler
    @mock.patch('crawler.containers.container.misc.process_is_crawler',
                side_effect=lambda pid: True if pid == '5' else False)
    def test_get_filtered_list(self, *args):
        pids = [c.pid for c in get_filtered_list_of_containers()]
        # pid 1 is the init process, which is not a container
        # according to the definition in container.py
        assert set(pids) == set(DOCKER_IDS + ['4'])
        assert '1' not in pids  # init process
        assert '5' not in pids  # crawler process

    @mock.patch('crawler.containers.list_docker_containers',
                side_effect=lambda container_opts, user_list='ALL':
                mocked_list_docker_containers(container_opts, user_list))
    @mock.patch('crawler.containers.container.namespace.get_pid_namespace',
                side_effect=lambda pid: pid)
    @mock.patch('crawler.containers.container.psutil.process_iter',
                side_effect=lambda: [PsUtilProcess('4'),  # container
                                     PsUtilProcess('1'),  # init
                                     PsUtilProcess('5')])  # crawler
    @mock.patch('crawler.containers.container.misc.process_is_crawler',
                side_effect=lambda pid: True if pid == '5' else False)
    def test_get_filtered_list_with_input_list(self, *args):
        opts = {'docker_containers_list': '102',
                'partition_strategy': {'name': 'equally_by_pid',
                                       'args': {'process_id': 0,
                                                'num_processes': 1}}}
        pids = [c.pid for c in get_filtered_list_of_containers(opts)]
        # pid 1 is the init process, which is not a container
        # according to the definition in container.py
        assert set(pids) == set(['102'])
        assert '3' not in pids  # filtered container
        assert '4' not in pids  # filtered container
        assert '1' not in pids  # init process
        assert '5' not in pids  # crawler process

    @mock.patch('crawler.containers.list_docker_containers',
                side_effect=lambda container_opts, user_list='ALL':
                mocked_list_docker_containers(container_opts, user_list))
    @mock.patch('crawler.containers.container.namespace.get_pid_namespace',
                side_effect=lambda pid: pid)
    @mock.patch('crawler.containers.container.psutil.process_iter',
                side_effect=lambda: [PsUtilProcess('4'),  # container
                                     PsUtilProcess('1'),  # init
                                     PsUtilProcess('5')])  # crawler
    @mock.patch('crawler.containers.container.misc.process_is_crawler',
                side_effect=lambda pid: True if pid == '5' else False)
    def test_get_filtered_list_with_input_list_ALL(self, *args):
        opts = {'docker_containers_list': 'ALL',
                'partition_strategy': {'name': 'equally_by_pid',
                                       'args': {'process_id': 0,
                                                'num_processes': 1}}}
        pids = [c.pid for c in get_filtered_list_of_containers(opts)]
        # pid 1 is the init process, which is not a container
        # according to the definition in container.py
        assert set(pids) == set(DOCKER_IDS + ['4'])

    @mock.patch('crawler.containers.list_docker_containers',
                side_effect=lambda container_opts, user_list='ALL':
                mocked_list_docker_containers(container_opts, user_list))
    @mock.patch('crawler.containers.container.namespace.get_pid_namespace',
                side_effect=lambda pid: pid)
    @mock.patch('crawler.containers.container.psutil.process_iter',
                side_effect=lambda: [PsUtilProcess('4'),  # container
                                     PsUtilProcess('1'),  # init
                                     PsUtilProcess('9')])  # crawler
    @mock.patch('crawler.containers.container.misc.process_is_crawler',
                side_effect=lambda pid: True if pid == '9' else False)
    def test_get_filtered_list_with_3_processes(self, *args):

        # Let's divide the lists for three procs: pids1, pids2, pids3
        opts = {'docker_containers_list': 'ALL',
                'partition_strategy': {'name': 'equally_by_pid',
                                       'args': {'process_id': 0,  # <P0
                                                'num_processes': 3}}}
        pids1 = [c.pid for c in get_filtered_list_of_containers(opts)]

        opts = {'docker_containers_list': 'ALL',
                'partition_strategy': {'name': 'equally_by_pid',
                                       'args': {'process_id': 1,  # <P1
                                                'num_processes': 3}}}
        pids2 = [c.pid for c in get_filtered_list_of_containers(opts)]

        opts = {'docker_containers_list': 'ALL',
                'partition_strategy': {'name': 'equally_by_pid',
                                       'args': {'process_id': 2,  # <P2
                                                'num_processes': 3}}}
        pids3 = [c.pid for c in get_filtered_list_of_containers(opts)]

        assert set(pids1 + pids2 + pids3) == set(DOCKER_IDS + ['4'])

    @mock.patch('crawler.containers.list_docker_containers',
                side_effect=lambda container_opts, user_list='ALL':
                mocked_list_docker_containers(container_opts, user_list))
    @mock.patch('crawler.containers.container.namespace.get_pid_namespace',
                side_effect=lambda pid: pid)
    @mock.patch('crawler.containers.container.psutil.process_iter',
                side_effect=lambda: [PsUtilProcess('4'),  # container
                                     PsUtilProcess('1'),  # init
                                     PsUtilProcess('5')])  # crawler
    @mock.patch('crawler.containers.container.misc.process_is_crawler',
                side_effect=lambda pid: True if pid == '5' else False)
    def test_get_filtered_list_non_default_env(self, *args):
        opts = {'environment': 'alchemy',
                'docker_containers_list': 'ALL',
                'partition_strategy': {'name': 'equally_by_pid',
                                       'args': {'process_id': 0,
                                                'num_processes': 1}}}
        pids = [c.pid for c in get_filtered_list_of_containers(opts)]
        # pid 1 is the init process, which is not a container
        # according to the definition in container.py
        assert set(pids) == set(DOCKER_IDS)
        # only docker containers are returned in non-cloudsight environments
        # (see the 'alchemy' above)
        assert '4' not in pids
