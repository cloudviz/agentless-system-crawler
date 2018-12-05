import unittest

import dateutil.parser as dp
import docker
import mock

import utils.dockerutils
from utils.crawler_exceptions import (DockerutilsNoJsonLog, DockerutilsException)


class MockedClient():

    def containers(self):
        return [{'Id': 'good_id'}]
    
    def networks(self):
        return [{'Name':'bridge', 'Id':'b7f7e3e6a2c204240a1ca334645d42c458cad466206c6f921082bb27b95b2d98'}] 

    def info(self):
        return {'Driver': 'btrfs'}

    def version(self):
        return {'Version': '1.10.1'}

    def inspect_container(self, id):
        return {
            "Id": "good_id",
            "Created": "2016-07-06",
            "State": {
                "Status": "running",
                "Running": True,
                "Pid": 11186
            },
            "Image": "sha256:07c86167cdc4264926fa5d2894e34a339ad27",
            "Name": "/pensive_rosalind",
            "Mounts": [],
            "LogPath": "/a/b/c/log.json",
            "Config": {
                    "Cmd": [
                        "bash"
                    ],
                "Image": "ubuntu:trusty"
            },
            "NetworkSettings": {
                "Ports": {
                    "80/tcp": [
                        {
                            "HostIp": "0.0.0.0",
                            "HostPort": "32768"
                        }
                    ]}

            },
            "HostConfig": {
                "PortBindings": {
                    "809/tcp": [
                        {
                            "HostIp": "",
                            "HostPort": ""
                        }
                    ]
                }

            }
        }

    def inspect_image(self, image_id):
        return {'RepoTags': ['registry/abc/def:latest', 'debian:latest']}

    def history(self, image_id):
        return [{'History': 'xxx'}]

    def docker_network(self, id):
        return [{
            "Name": "bridge",
            "Id": "b7f7e3e6a2c204240a1ca334645d42c458cad466206c6f921082bb27b95b2d98",
            "Created": "2018-11-12T05:10:12.622525664Z",
            "Scope": "local",
            "Driver": "bridge",
            "EnableIPv6": false,
            "Internal": false,
            "Attachable": false,
            "Ingress": false,
            "ConfigOnly": false,
            "Containers": {},
            "Options": {
                  "com.docker.network.bridge.default_bridge": "true",
                  "com.docker.network.bridge.enable_icc": "true",
                  "com.docker.network.bridge.enable_ip_masquerade": "true",
                  "com.docker.network.bridge.host_binding_ipv4": "0.0.0.0",
                  "com.docker.network.bridge.name": "docker0",
                  "com.docker.network.driver.mtu": "1500"
            },
            "Labels": {}
        }]

def throw_runtime_error(*args, **kwargs):
    raise RuntimeError()


def throw_io_error(*args, **kwargs):
    raise IOError()


def throw_docker_exception(*args, **kwargs):
    raise docker.errors.DockerException()


class DockerUtilsTests(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    @mock.patch('utils.dockerutils.docker.Client',
                side_effect=lambda base_url, version: MockedClient())
    def test_exec_dockerps(self, *args):
        for c in utils.dockerutils.exec_dockerps():
            print c
            break

        docker_datetime = dp.parse('2016-07-06')
        epoch_seconds = docker_datetime.strftime('%s')

        assert c == {'Name': '/pensive_rosalind',
                     'Created': epoch_seconds,
                     'RepoTag': 'registry/abc/def:latest',
                     'RepoTags': ['registry/abc/def:latest', 'debian:latest'],
                     'State': {'Status': 'running',
                               'Running': True,
                               'Pid': '11186'},
                     'Mounts': [],
                     'Config': {'Image': 'ubuntu:trusty',
                                'Cmd': ['bash']},
                     'NetworkSettings': {'Ports': {
                                         '80/tcp': [{'HostPort': '32768',
                                                     'HostIp': '0.0.0.0'}]}},
                     'Image': 'sha256:07c86167cdc4264926fa5d2894e34a339ad27',
                     'LogPath': '/a/b/c/log.json',
                     'HostConfig': {'PortBindings': {
                                    '809/tcp': [{'HostPort': '',
                                                 'HostIp': ''}]}},
                     'Id': 'good_id'}

    @mock.patch('utils.dockerutils.docker.Client',
                side_effect=lambda base_url, version: MockedClient())
    @mock.patch('utils.dockerutils.exec_dockerinspect',
                side_effect=throw_docker_exception)
    def test_exec_dockerps_failure(self, *args):
        with self.assertRaises(DockerutilsException):
            utils.dockerutils.exec_dockerps()

    @mock.patch('utils.dockerutils.docker.Client',
                side_effect=lambda base_url, version: MockedClient())
    def test_exec_docker_history(self, *args):
        h = utils.dockerutils.exec_docker_history('ididid')
        assert h == [{'History': 'xxx'}]

    @mock.patch('utils.dockerutils.docker.Client',
                side_effect=throw_docker_exception)
    def test_exec_docker_history_failure(self, *args):
        with self.assertRaises(DockerutilsException):
            utils.dockerutils.exec_docker_history('ididid')

    @mock.patch('utils.dockerutils.docker.Client',
                side_effect=lambda base_url, version: MockedClient())
    def test_exec_dockernetwork(self, *args):
        net = utils.dockerutils.exec_dockernetwork('ididid')
        assert net == {'usesDocker0Bridge': False}

    @mock.patch('utils.dockerutils.docker.Client',
                side_effect=lambda base_url, version: MockedClient())
    def test_exec_docker_inspect(self, *args):
        i = utils.dockerutils.exec_dockerinspect('ididid')

        docker_datetime = dp.parse('2016-07-06')
        epoch_seconds = docker_datetime.strftime('%s')

        assert i == {'Name': '/pensive_rosalind',
                     'Created': epoch_seconds,
                     'RepoTag': 'registry/abc/def:latest',
                     'RepoTags': ['registry/abc/def:latest', 'debian:latest'],
                     'State': {'Status': 'running',
                               'Running': True,
                               'Pid': '11186'},
                     'Mounts': [],
                     'Config': {'Image': 'ubuntu:trusty',
                                'Cmd': ['bash']},
                     'NetworkSettings': {'Ports': {
                                         '80/tcp': [
                                             {'HostPort': '32768',
                                              'HostIp': '0.0.0.0'}]}},
                     'Image': 'sha256:07c86167cdc4264926fa5d2894e34a339ad27',
                     'LogPath': '/a/b/c/log.json',
                     'HostConfig': {'PortBindings': {
                                    '809/tcp': [{'HostPort': '',
                                                 'HostIp': ''}]}},
                     'Id': 'good_id'}

    @mock.patch('utils.dockerutils.docker.Client',
                side_effect=throw_docker_exception)
    def test_exec_docker_inspect_failure(self, *args):
        with self.assertRaises(DockerutilsException):
            utils.dockerutils.exec_dockerinspect('ididid')

    @mock.patch('utils.dockerutils.docker.Client',
                side_effect=throw_docker_exception)
    @mock.patch('utils.dockerutils.open')
    def test_get_docker_storage_driver_step1a(self, mock_open, mock_client):

        mock_open.return_value = open('tests/unit/proc_mounts_aufs')
        assert utils.dockerutils._get_docker_storage_driver() == 'aufs'
        mock_open.return_value = open('tests/unit/proc_mounts_devicemapper')
        assert utils.dockerutils._get_docker_storage_driver() == 'devicemapper'
        mock_open.return_value = open('tests/unit/proc_mounts_vfs')
        assert utils.dockerutils._get_docker_storage_driver() == 'vfs'
        mock_open.return_value = open('tests/unit/proc_mounts_btrfs')
        assert utils.dockerutils._get_docker_storage_driver() == 'btrfs'

    @mock.patch('utils.dockerutils.docker.Client',
                side_effect=lambda base_url, version: MockedClient())
    @mock.patch('utils.dockerutils.open',
                side_effect=throw_io_error)
    def test_get_docker_storage_driver_step2(self, mock_open, mock_client):
        assert utils.dockerutils._get_docker_storage_driver() == 'btrfs'

    @mock.patch('utils.dockerutils.docker.Client',
                side_effect=throw_docker_exception)
    @mock.patch('utils.dockerutils.open',
                side_effect=throw_io_error)
    def test_get_docker_storage_driver_failure(self, mock_open, mock_client):
        assert utils.dockerutils._get_docker_storage_driver() == 'devicemapper'

    @mock.patch('utils.dockerutils.docker.Client',
                side_effect=lambda base_url, version: MockedClient())
    def test_get_docker_server_version(self, mock_client):
        assert utils.dockerutils._get_docker_server_version() == '1.10.1'

    @mock.patch('utils.dockerutils.docker.Client',
                side_effect=throw_docker_exception)
    def test_get_docker_server_version_failure(self, mock_client):
        with self.assertRaises(DockerutilsException):
            utils.dockerutils._get_docker_server_version()

    @mock.patch('utils.dockerutils.docker.Client',
                side_effect=lambda base_url, version: MockedClient())
    @mock.patch(
        'crawler.utils.dockerutils.os.path.isfile',
        side_effect=lambda p:
            True if p == ("/var/lib/docker/containers/id/id-json.log")
            else False)
    def test_get_json_logs_path_from_path(self, mock_isfile, mock_client):
        assert utils.dockerutils.get_docker_container_json_logs_path(
            'id') == '/var/lib/docker/containers/id/id-json.log'

    @mock.patch('utils.dockerutils.docker.Client',
                side_effect=lambda base_url, version: MockedClient())
    @mock.patch('utils.dockerutils.os.path.isfile',
                side_effect=lambda p:
                    True if p == '/a/b/c/log.json' else False)
    def test_get_json_logs_path_from_daemon(self, mock_isfile, mock_client):
        assert utils.dockerutils.get_docker_container_json_logs_path(
            'id') == '/a/b/c/log.json'

    @mock.patch('utils.dockerutils.docker.Client',
                side_effect=lambda base_url, version: MockedClient())
    @mock.patch('utils.dockerutils.os.path.isfile',
                side_effect=lambda p: False)
    def test_get_json_logs_path_failure(self, mock_isfile, mock_client):
        with self.assertRaises(DockerutilsNoJsonLog):
            utils.dockerutils.get_docker_container_json_logs_path('id')

    @mock.patch('utils.dockerutils.docker.Client',
                side_effect=lambda base_url, version: MockedClient())
    @mock.patch('utils.dockerutils.open',
                side_effect=throw_io_error)
    def test_get_rootfs_not_supported_driver_failure(
            self, mock_open, mock_client):
        utils.dockerutils.driver = 'not_supported_driver'
        with self.assertRaises(DockerutilsException):
            utils.dockerutils.get_docker_container_rootfs_path('id')

    @mock.patch('utils.dockerutils.docker.Client',
                side_effect=lambda base_url, version: MockedClient())
    @mock.patch('utils.dockerutils.open',
                side_effect=[open('tests/unit/proc_pid_mounts_devicemapper'),
                             open('tests/unit/proc_mounts_devicemapper')])
    def test_get_rootfs_devicemapper(self, mock_open, mock_client):
        utils.dockerutils.driver = 'devicemapper'
        assert utils.dockerutils.get_docker_container_rootfs_path(
            'id') == ("/var/lib/docker/devicemapper/mnt/"
                      "65fe676c24fe1faea1f06e222cc3811cc"
                      "9b651c381702ca4f787ffe562a5e39b/rootfs")

    @mock.patch('utils.dockerutils.docker.Client',
                side_effect=lambda base_url, version: MockedClient())
    @mock.patch('utils.dockerutils.open',
                side_effect=throw_io_error)
    def test_get_rootfs_devicemapper_failure(self, mock_open, mock_client):
        utils.dockerutils.driver = 'devicemapper'
        with self.assertRaises(DockerutilsException):
            utils.dockerutils.get_docker_container_rootfs_path('id')

    @mock.patch('utils.dockerutils.misc.btrfs_list_subvolumes',
                side_effect=lambda p:
                [
                    ('ID', '260', 'gen', '22', 'top',
                     'level', '5', 'path', 'sub1/abcde'),
                    ('ID', '260', 'gen', '22', 'top',
                     'level', '5', 'path', 'sub1/abcde/sub2'),
                ]
                )
    @mock.patch('utils.dockerutils.docker.Client',
                side_effect=lambda base_url, version: MockedClient())
    def test_get_rootfs_btrfs_v1_8(self, mock_client, mock_list):
        utils.dockerutils.driver = 'btrfs'
        utils.dockerutils.server_version = '1.8.0'
        assert utils.dockerutils.get_docker_container_rootfs_path(
            'abcde') == '/var/lib/docker/sub1/abcde'

    @mock.patch('utils.dockerutils.misc.btrfs_list_subvolumes',
                side_effect=throw_runtime_error)
    @mock.patch('utils.dockerutils.docker.Client',
                side_effect=lambda base_url, version: MockedClient())
    def test_get_rootfs_btrfs_v1_8_failure(self, mock_client, mock_list):
        utils.dockerutils.driver = 'btrfs'
        utils.dockerutils.server_version = '1.8.0'
        with self.assertRaises(DockerutilsException):
            utils.dockerutils.get_docker_container_rootfs_path('abcde')

    @mock.patch('utils.dockerutils.docker.Client',
                side_effect=lambda base_url, version: MockedClient())
    @mock.patch('utils.dockerutils.open',
                side_effect=[open('tests/unit/btrfs_mount_init-id')])
    def test_get_rootfs_btrfs_v1_10(self, mock_open, mock_client):
        utils.dockerutils.driver = 'btrfs'
        utils.dockerutils.server_version = '1.10.0'
        assert utils.dockerutils.get_docker_container_rootfs_path(
            'id') == '/var/lib/docker/btrfs/subvolumes/vol1/id/rootfs-a-b-c'

    @mock.patch('utils.dockerutils.docker.Client',
                side_effect=lambda base_url, version: MockedClient())
    @mock.patch('utils.dockerutils.open',
                side_effect=throw_io_error)
    def test_get_rootfs_btrfs_v1_10_failure(self, mock_open, mock_client):
        utils.dockerutils.driver = 'btrfs'
        utils.dockerutils.server_version = '1.10.0'
        with self.assertRaises(DockerutilsException):
            utils.dockerutils.get_docker_container_rootfs_path('abcde')

    @mock.patch('utils.dockerutils.os.path.isdir',
                side_effect=lambda d: True)
    @mock.patch('utils.dockerutils.os.listdir',
                side_effect=lambda d: ['usr', 'boot', 'var'])
    @mock.patch('utils.dockerutils.docker.Client',
                side_effect=lambda base_url, version: MockedClient())
    def test_get_rootfs_aufs_v1_8(self, *args):
        utils.dockerutils.driver = 'aufs'
        utils.dockerutils.server_version = '1.8.0'
        assert utils.dockerutils.get_docker_container_rootfs_path(
            'abcde') == '/var/lib/docker/aufs/mnt/abcde'

    @mock.patch('utils.dockerutils.os.path.isdir',
                side_effect=lambda d: False)
    @mock.patch('utils.dockerutils.os.listdir',
                side_effect=lambda d: ['usr', 'boot', 'var'])
    @mock.patch('utils.dockerutils.docker.Client',
                side_effect=lambda base_url, version: MockedClient())
    def test_get_rootfs_aufs_v1_8_failure(self, *args):
        utils.dockerutils.driver = 'aufs'
        utils.dockerutils.server_version = '1.8.0'
        with self.assertRaises(DockerutilsException):
            utils.dockerutils.get_docker_container_rootfs_path('abcde')

    @mock.patch('utils.dockerutils.docker.Client',
                side_effect=lambda base_url, version: MockedClient())
    @mock.patch('utils.dockerutils.open',
                side_effect=[open('tests/unit/aufs_mount_init-id')])
    def test_get_rootfs_aufs_v1_10(self, *args):
        utils.dockerutils.driver = 'aufs'
        utils.dockerutils.server_version = '1.10.0'
        assert utils.dockerutils.get_docker_container_rootfs_path(
            'abcde') == '/var/lib/docker/aufs/mnt/vol1/id/rootfs-a-b-c'

    @mock.patch('utils.dockerutils.docker.Client',
                side_effect=lambda base_url, version: MockedClient())
    @mock.patch('utils.dockerutils.open',
                side_effect=throw_io_error)
    def test_get_rootfs_aufs_v1_10_failure(self, *args):
        utils.dockerutils.driver = 'aufs'
        utils.dockerutils.server_version = '1.10.0'
        with self.assertRaises(DockerutilsException):
            utils.dockerutils.get_docker_container_rootfs_path('abcde')

    @mock.patch('utils.dockerutils.docker.Client',
                side_effect=lambda base_url, version: MockedClient())
    @mock.patch('utils.dockerutils.open',
                side_effect=[open('tests/unit/vfs_mount_init-id')])
    def test_get_rootfs_vfs_v1_10(self, *args):
        utils.dockerutils.driver = 'vfs'
        utils.dockerutils.server_version = '1.10.0'
        assert utils.dockerutils.get_docker_container_rootfs_path(
            'abcde') == '/var/lib/docker/vfs/dir/vol1/id/rootfs-a-b-c'

    @mock.patch('utils.dockerutils.docker.Client',
                side_effect=lambda base_url, version: MockedClient())
    @mock.patch('utils.dockerutils.open',
                side_effect=throw_io_error)
    def test_get_rootfs_vfs_v1_10_failure(self, *args):
        utils.dockerutils.driver = 'vfs'
        utils.dockerutils.server_version = '1.10.0'
        with self.assertRaises(DockerutilsException):
            utils.dockerutils.get_docker_container_rootfs_path('abcde')
