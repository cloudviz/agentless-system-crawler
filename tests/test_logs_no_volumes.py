import unittest
import tempfile
import os
import shutil

from crawler import dockerutils
from crawler import dockercontainer

# Tests dockercontainer._get_logfiles_list
# for the case when no volumes are mounted


def get_docker_container_rootfs_path(long_id, inspect):
    return "rootfs"


def get_container_log_files(path, options):
    pass


class DockerContainerTests(unittest.TestCase):

    def setUp(self):

        self.host_log_dir = tempfile.mkdtemp(prefix='host_log_dir.')
        self.volume = tempfile.mkdtemp(prefix='volume.')
        for logf in ['test1.log', 'test2.log']:
            with open(os.path.join(self.volume, logf), 'w') as logp:
                logp.write(logf)

        self.inspect = \
            {
                "Id": "1e744b5e3e11e848863fefe9d9a8b3731070c6b0c702a04d2b8ab948ea24e847",
                "Created": "2016-07-06T16:38:05.479090842Z",
                "State": {
                    "Status": "running",
                    "Running": True,
                    "Pid": 11186
                },
                "Image": "sha256:07c86167cdc4264926fa5d2894e34a339ad27f730e8cc81a16cd21b7479e8eac",
                "Name": "/pensive_rosalind",
                "LogPath": "/var/lib/docker/containers/1e744b5e3e11e848863fefe9d9a8b3731070c6b0c702a04d2b8ab948ea24e847/1e744b5e3e11e848863fefe9d9a8b3731070c6b0c702a04d2b8ab948ea24e847-json.log",
                "HostnamePath": "/var/lib/docker/containers/1e744b5e3e11e848863fefe9d9a8b3731070c6b0c702a04d2b8ab948ea24e847/hostname",
                "Mounts": [],
                "Config": {
                    "Cmd": [
                        "bash"
                    ],
                    "Image": "ubuntu:trusty"
                },
                "docker_image_long_name": "long_name/short_name",
                "docker_image_short_name": "short_name",
                "docker_image_tag": "image_tag",
                "docker_image_registry": "image_registry",
                "owner_namespace": "owner_namespace",
                "NetworkSettings": {
                }
            }
        self.docker_container = dockercontainer.\
            DockerContainer(self.inspect['Id'], self.inspect)

        dockerutils.get_docker_container_rootfs_path = \
            get_docker_container_rootfs_path

        self.docker_container._get_container_log_files = get_container_log_files
        self.docker_container.log_file_list = [
            {'name': '/data/test1.log', 'type': None}]

    def tearDown(self):
        shutil.rmtree(self.volume)
        shutil.rmtree(self.host_log_dir)

    def test_get_logfiles_list(self):
        log_list = self.docker_container._get_logfiles_list(
            self.host_log_dir, {})
        for log_dict in log_list:
            if log_dict['name'] == '/data/test1.log':
                self.assertEqual(
                    log_dict['dest'], self.host_log_dir +
                    '/data/test1.log'
                )

if __name__ == '__main__':
    logging.basicConfig(filename='test_dockerutils.log', filemode='a',
                        format='%(asctime)s %(levelname)s : %(message)s', level=logging.DEBUG)

    unittest.main()
