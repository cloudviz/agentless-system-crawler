import mock
import unittest
import os
import requests
import copy
import shutil

from crawler import crawler_exceptions
from crawler.dockercontainer import DockerContainer, list_docker_containers

def mocked_exists(pid):
    return True

def mocked_docker_inspect(long_id):
    if long_id == 'no_container_id':
        raise requests.exceptions.HTTPError
    else:
        inspect = {
                "Id": "good_id",
                "Created": "2016-07-06T16:38:05.479090842Z",
                "State": {
                    "Status": "running",
                    "Running": True,
                    "Pid": 11186
                },
                "Image": "sha256:07c86167cdc4264926fa5d2894e34a339ad27",
                "Name": "/pensive_rosalind",
                "Mounts": [],
                "Config": {
                    "Cmd": [
                        "bash"
                    ],
                    "Image": "ubuntu:trusty"
                },
                "NetworkSettings": {
                }
            }
    inspect['Id'] = long_id
    return inspect

def mocked_exec_dockerps():
    inspect1 = {
                "Id": "good_id",
                "Created": "2016-07-06T16:38:05.479090842Z",
                "State": {
                    "Status": "running",
                    "Running": True,
                    "Pid": 11186
                },
                "Image": "sha256:07c86167cdc4264926fa5d2894e34a339ad27",
                "Name": "/pensive_rosalind",
                "Mounts": [],
                "Config": {
                    "Cmd": [
                        "bash"
                    ],
                    "Image": "ubuntu:trusty"
                },
                "NetworkSettings": {
                }
            }
    inspect2 = {
                "Id": "no_namespace",
                "Created": "2016-07-06T16:38:05.479090842Z",
                "State": {
                    "Status": "running",
                    "Running": True,
                    "Pid": 11186
                },
                "Image": "sha256:07c86167cdc4264926fa5d2894e34a339ad27",
                "Name": "/pensive_rosalind",
                "Mounts": [],
                "Config": {
                    "Cmd": [
                        "bash"
                    ],
                    "Image": "ubuntu:trusty"
                },
                "NetworkSettings": {
                }
            }
    inspect3 = {
                "Id": "good_id",
                "Created": "2016-07-06T16:38:05.479090842Z",
                "State": {
                    "Status": "running",
                    "Running": True,
                    "Pid": 11186
                },
                "Image": "sha256:07c86167cdc4264926fa5d2894e34a339ad27",
                "Name": "/pensive_rosalind",
                "Mounts": [],
                "Config": {
                    "Cmd": [
                        "bash"
                    ],
                    "Image": "ubuntu:trusty"
                },
                "NetworkSettings": {
                }
            }
    return [inspect1, inspect2, inspect3]

def mocked_get_rootfs(long_id):
    if long_id == 'valid_rootfs_id':
        return '/tmp/something/docker/' + long_id
    else:
        raise requests.exceptions.HTTPError

def mocked_symlink_oserror(a,b):
    raise OSError()

def mocked_symlink_exception(a,b):
    raise Exception()

def mocked_rmtree_exception(path):
    raise OSError()

class MockedRuntimeEnv():
    def get_environment_name(self):
        return 'cloudsight'
    def get_container_namespace(self, long_id, options):
        if long_id == 'good_id':
            return 'random_namespace'
        elif long_id == 'throw_non_handled_exception_id':
            raise Exception()
        elif long_id == 'throw_bad_environment_exception_id':
            raise crawler_exceptions.ContainerInvalidEnvironment()
        elif long_id == 'no_namespace':
            return None
        else:
            return 'other_namespace'
    def get_container_log_file_list(self, long_id, options):
        logs = copy.deepcopy(options['container_logs'])
        if long_id == 'good_id':
            logs.extend([{'name':'/var/log/1', 'type':None}, {'name':'/var/log/2', 'type':None}])
        elif long_id == 'throw_value_error_id':
            raise ValueError()
        elif long_id == 'valid_rootfs_id':
            logs.extend([{'name':'/var/log/1', 'type':None}, {'name':'/var/log/2', 'type':None}, {'name':'../../as','type':None}])
        return logs
    def get_container_log_prefix(self, long_id, options):
        return 'random_prefix'

def mocked_get_runtime_env():
    return MockedRuntimeEnv()

@mock.patch('crawler.dockercontainer.exec_dockerps',
            side_effect=mocked_exec_dockerps)
@mock.patch('crawler.dockercontainer.plugins_manager.get_runtime_env_plugin',
            side_effect=mocked_get_runtime_env)
@mock.patch('crawler.dockercontainer.exec_dockerinspect',
            side_effect=mocked_docker_inspect)
@mock.patch('crawler.dockercontainer.get_docker_container_rootfs_path',
            side_effect=mocked_get_rootfs)
class DockerDockerContainerTests(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_list_docker_containers(self, mock_get_rootfs, mock_inspect, mocked_get_runtime_env, mocked_dockerps):
        n = 0
        for c in list_docker_containers():
            assert c.long_id == 'good_id'
            n += 1
        assert mocked_get_runtime_env.call_count == 3
        assert n == 2

    def test_list_docker_containers_with_opts(self, mock_get_rootfs, mock_inspect, mocked_get_runtime_env, mocked_dockerps):
        n = 0
        for c in list_docker_containers({'long_id_to_namespace_map':{'good_id':'good_id_namespace'}}):
            assert c.long_id == 'good_id'
            assert c.namespace == 'good_id_namespace'
            n += 1
        # get_namespace from the runtime_env is called only once because of the map
        assert mocked_get_runtime_env.call_count == 1
        assert n == 2

    def test_init(self, mock_get_rootfs, mock_inspect, mocked_get_runtime_env, mocked_dockerps):
        c = DockerContainer("good_id")
        mock_inspect.assert_called()
        assert not c.root_fs
        assert mocked_get_runtime_env.call_count == 1

    def test_init_from_inspect(self, mock_get_rootfs, mock_inspect, mocked_get_runtime_env, mocked_dockerps):
        inspect = {
                "Id": "good_id",
                "Created": "2016-07-06T16:38:05.479090842Z",
                "State": {
                    "Status": "running",
                    "Running": True,
                    "Pid": 11186
                },
                "Image": "sha256:07c86167cdc4264926fa5d2894e34a339ad27",
                "Name": "/pensive_rosalind",
                "Mounts": [],
                "Config": {
                    "Cmd": [
                        "bash"
                    ],
                    "Image": "ubuntu:trusty"
                },
                "NetworkSettings": {
                }
            }
        c = DockerContainer("good_id", inspect)
        mock_inspect.assert_not_called()
        assert not c.root_fs
        assert mocked_get_runtime_env.call_count == 1

    def test_init_from_inspect_w_repotags(self, mock_get_rootfs, mock_inspect, mocked_get_runtime_env, mocked_dockerps):
        inspect = {
                "Id": "good_id",
                "Created": "2016-07-06T16:38:05.479090842Z",
                "State": {
                    "Status": "running",
                    "Running": True,
                    "Pid": 11186
                },
                "Image": "sha256:07c86167cdc4264926fa5d2894e34a339ad27",
                "Name": "/pensive_rosalind",
                "Mounts": [],
                "Config": {
                    "Cmd": [
                        "bash"
                    ],
                    "Image": "ubuntu:trusty"
                },
                "NetworkSettings": {
                },
                'RepoTag': 'registry.com:123/ric/img:latest'
            }
        c = DockerContainer("good_id", inspect)
        mock_inspect.assert_not_called()
        assert not c.root_fs
        assert mocked_get_runtime_env.call_count == 1
        assert c.docker_image_long_name == 'registry.com:123/ric/img:latest'
        assert c.docker_image_short_name == 'img:latest'
        assert c.docker_image_tag == 'latest'
        assert c.docker_image_registry == 'registry.com:123'
        assert c.owner_namespace == 'ric'

    def test_init_from_inspect_w_repotags2(self, mock_get_rootfs, mock_inspect, mocked_get_runtime_env, mocked_dockerps):
        inspect = {
                "Id": "good_id",
                "Created": "2016-07-06T16:38:05.479090842Z",
                "State": {
                    "Status": "running",
                    "Running": True,
                    "Pid": 11186
                },
                "Image": "sha256:07c86167cdc4264926fa5d2894e34a339ad27",
                "Name": "/pensive_rosalind",
                "Mounts": [],
                "Config": {
                    "Cmd": [
                        "bash"
                    ],
                    "Image": "ubuntu:trusty"
                },
                "NetworkSettings": {
                },
                'RepoTag': 'registry.com:123/img:latest'
            }
        c = DockerContainer("good_id", inspect)
        mock_inspect.assert_not_called()
        assert not c.root_fs
        assert mocked_get_runtime_env.call_count == 1
        assert c.docker_image_long_name == 'registry.com:123/img:latest'
        assert c.docker_image_short_name == 'img:latest'
        assert c.docker_image_tag == 'latest'
        assert c.docker_image_registry == 'registry.com:123'
        assert c.owner_namespace == ''

    def test_init_failed(self, mock_get_rootfs, mock_inspect, mocked_get_runtime_env, mocked_dockerps):
        with self.assertRaises(crawler_exceptions.ContainerNonExistent):
            c = DockerContainer("no_container_id")
        assert mocked_get_runtime_env.call_count == 0

    def test_init_wrong_environment(self, mock_get_rootfs, mock_inspect, mocked_get_runtime_env, mocked_dockerps):
        with self.assertRaises(crawler_exceptions.ContainerInvalidEnvironment):
            c = DockerContainer("no_namespace")
        with self.assertRaises(crawler_exceptions.ContainerInvalidEnvironment):
            c = DockerContainer("throw_bad_environment_exception_id")
        with self.assertRaises(Exception):
            c = DockerContainer("throw_non_handled_exception_id")
        with self.assertRaises(crawler_exceptions.ContainerInvalidEnvironment):
            c = DockerContainer("throw_value_error_id")

    def test_is_docker(self, mock_get_rootfs, mock_inspect, mocked_get_runtime_env, mocked_dockerps):
        c = DockerContainer("good_id")
        assert c.is_docker_container()
        print(c)

    @mock.patch('crawler.dockercontainer.os.path.ismount', side_effect=lambda x: True if x == '/cgroup/memory' else False)
    def test_memory_cgroup(self, mocked_ismount, mock_get_rootfs, mock_inspect, mocked_get_runtime_env, mocked_dockerps):
        c = DockerContainer("good_id")
        assert c.get_memory_cgroup_path('abc') == '/cgroup/memory/docker/good_id/abc'

    @mock.patch('crawler.dockercontainer.os.path.ismount', side_effect=lambda x: True if x == '/cgroup/cpuacct' else False)
    def test_cpu_cgroup(self, mocked_ismount, mock_get_rootfs, mock_inspect, mocked_get_runtime_env, mocked_dockerps):
        c = DockerContainer("good_id")
        assert c.get_cpu_cgroup_path('abc') == '/cgroup/cpuacct/docker/good_id/abc'

    @mock.patch('crawler.dockercontainer.os.makedirs')
    @mock.patch('crawler.dockercontainer.os.symlink')
    def test_link_logfiles(self, mock_symlink, mock_makedirs, mock_get_rootfs, mock_inspect, mocked_get_runtime_env, mocked_dockerps):
        c = DockerContainer("valid_rootfs_id")
        c.link_logfiles()
        mock_symlink.assert_called_with(
            '/tmp/something/docker/valid_rootfs_id/var/log/2',
            '/var/log/crawler_container_logs/random_prefix/var/log/2')
        assert mock_symlink.call_count == 4

    @mock.patch('crawler.dockercontainer.os.makedirs')
    @mock.patch('crawler.dockercontainer.os.symlink')
    @mock.patch('crawler.dockercontainer.misc.GetProcessEnv',
                side_effect=lambda x : {'LOG_LOCATIONS':'/var/env/1,/var/env/2'})
    def test_link_logfiles_env_variable(self, mock_get_env, mock_symlink, mock_makedirs, mock_get_rootfs, mock_inspect, mocked_get_runtime_env, mocked_dockerps):
        c = DockerContainer("valid_rootfs_id")
        c.link_logfiles()
        mock_symlink.assert_called_with(
            '/tmp/something/docker/valid_rootfs_id/var/log/2',
            '/var/log/crawler_container_logs/random_prefix/var/log/2')
        assert mock_symlink.call_count == 6

    @mock.patch('crawler.dockercontainer.os.makedirs')
    @mock.patch('crawler.dockercontainer.os.symlink',
                side_effect=mocked_symlink_oserror)
    def test_link_logfiles_symlink_oserror(self, mock_symlink, mock_makedirs, mock_get_rootfs, mock_inspect, mocked_get_runtime_env, mocked_dockerps):
        c = DockerContainer("valid_rootfs_id")
        c.link_logfiles()
        # no exceptoin should be thrown

    @mock.patch('crawler.dockercontainer.os.makedirs')
    @mock.patch('crawler.dockercontainer.os.symlink',
                side_effect=mocked_symlink_exception)
    def test_link_logfiles_symlink_exception(self, mock_symlink, mock_makedirs, mock_get_rootfs, mock_inspect, mocked_get_runtime_env, mocked_dockerps):
        c = DockerContainer("valid_rootfs_id")
        c.link_logfiles()
        # no exceptoin should be thrown

    @mock.patch('crawler.dockercontainer.os.makedirs')
    @mock.patch('crawler.dockercontainer.os.symlink')
    @mock.patch('crawler.dockercontainer.shutil.rmtree')
    def test_link_and_unlink_logfiles(self, mock_rmtree, mock_symlink, mock_makedirs, mock_get_rootfs, mock_inspect, mocked_get_runtime_env, mocked_dockerps):
        c = DockerContainer("valid_rootfs_id")
        c.link_logfiles()
        mock_symlink.assert_called_with(
            '/tmp/something/docker/valid_rootfs_id/var/log/2',
            '/var/log/crawler_container_logs/random_prefix/var/log/2')
        c.unlink_logfiles()
        assert mock_symlink.call_count == 4
        assert mock_rmtree.call_count == 1

    @mock.patch('crawler.dockercontainer.os.makedirs')
    @mock.patch('crawler.dockercontainer.os.symlink')
    @mock.patch('crawler.dockercontainer.shutil.rmtree',
                side_effect=mocked_rmtree_exception)
    def test_link_and_unlink_logfiles_failed_rmtree(self, mock_rmtree, mock_symlink, mock_makedirs, mock_get_rootfs, mock_inspect, mocked_get_runtime_env, mocked_dockerps):
        c = DockerContainer("valid_rootfs_id")
        c.link_logfiles()
        mock_symlink.assert_called_with(
            '/tmp/something/docker/valid_rootfs_id/var/log/2',
            '/var/log/crawler_container_logs/random_prefix/var/log/2')
        c.unlink_logfiles()
        assert mock_symlink.call_count == 4
        assert mock_rmtree.call_count == 1

    @mock.patch('crawler.dockercontainer.os.makedirs')
    @mock.patch('crawler.dockercontainer.os.symlink')
    @mock.patch('crawler.dockercontainer.shutil.rmtree',
                side_effect=mocked_rmtree_exception)
    def test_links_with_mounts(self, mock_rmtree, mock_symlink, mock_makedirs, mock_get_rootfs, mock_inspect, mocked_get_runtime_env, mocked_dockerps):
        inspect = {
                "Id": "valid_rootfs_id",
                "Created": "2016-07-06T16:38:05.479090842Z",
                "State": {
                    "Status": "running",
                    "Running": True,
                    "Pid": 11186
                },
                "Image": "sha256:07c86167cdc4264926fa5d2894e34a339ad27",
                "Name": "/pensive_rosalind",
                # /var in the container is mapped to /mount/in/the/host
                # container was started with -v /var/in/the/host:/var
                "Mounts": [{'Source':'/var/in/the/host',
                            'Destination':'/var'}],
                "Config": {
                    "Cmd": [
                        "bash"
                    ],
                    "Image": "ubuntu:trusty"
                },
                "NetworkSettings": {
                }
            }
        c = DockerContainer("valid_rootfs_id", inspect)
        c.link_logfiles()
        mock_symlink.assert_called_with(
            '/var/in/the/host/log/2',
            '/var/log/crawler_container_logs/random_prefix/var/log/2')
        c.unlink_logfiles()
        assert mock_symlink.call_count == 4

    @mock.patch('crawler.dockercontainer.os.makedirs')
    @mock.patch('crawler.dockercontainer.os.symlink')
    @mock.patch('crawler.dockercontainer.shutil.rmtree',
                side_effect=mocked_rmtree_exception)
    # In older docker versions, the inspect field for Mounts was called Volumes
    def test_links_with_volumes(self, mock_rmtree, mock_symlink, mock_makedirs, mock_get_rootfs, mock_inspect, mocked_get_runtime_env, mocked_dockerps):
        inspect = {
                "Id": "valid_rootfs_id",
                "Created": "2016-07-06T16:38:05.479090842Z",
                "State": {
                    "Status": "running",
                    "Running": True,
                    "Pid": 11186
                },
                "Image": "sha256:07c86167cdc4264926fa5d2894e34a339ad27",
                "Name": "/pensive_rosalind",
                # /var in the container is mapped to /mount/in/the/host
                # container was started with -v /var/in/the/host:/var
                "Volumes": {'/var':'/var/in/the/host'},
                "Config": {
                    "Cmd": [
                        "bash"
                    ],
                    "Image": "ubuntu:trusty"
                },
                "NetworkSettings": {
                }
            }
        c = DockerContainer("valid_rootfs_id", inspect)
        c.link_logfiles()
        mock_symlink.assert_called_with(
            '/var/in/the/host/log/2',
            '/var/log/crawler_container_logs/random_prefix/var/log/2')
        c.unlink_logfiles()
        assert mock_symlink.call_count == 4

    # TODO test _get_cgroup_dir when ismount fails

    def _test_non_implemented_methods(self):
        with self.assertRaises(NotImplementedError):
            c.get_memory_cgroup_path()
        with self.assertRaises(NotImplementedError):
            c.get_cpu_cgroup_path()
        with self.assertRaises(NotImplementedError):
            c.link_logfiles()
        with self.assertRaises(NotImplementedError):
            c.unlink_logfiles()

    @mock.patch('crawler.emitter.os.path.exists', side_effect=mocked_exists)
    def _test_is_running(self, mock_exists):
        c = DockerContainer("good_id")
        assert c.is_running()

    def _test_eq_ne(self):
        c1 = DockerContainer("good_id")
        c2 = DockerContainer("ebcd")
        c3 = DockerContainer("ebcd")
        assert c1 != c2
        assert c2 == c3

    def _test_to_str(self):
        c = DockerContainer("good_id")
        print(c)
