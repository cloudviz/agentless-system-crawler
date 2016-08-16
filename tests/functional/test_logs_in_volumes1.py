import unittest
import tempfile
import os
import shutil
import mock

import crawler.dockerutils
import crawler.dockercontainer

# Tests dockercontainer._get_logfiles_list
# the log file, test1.log is in a host directory
# mounted as volume


def get_container_log_files(path, options):
    pass


@mock.patch('crawler.dockercontainer.get_docker_container_rootfs_path',
            side_effect=lambda id : 'rootfs')
class DockerContainerTests(unittest.TestCase):

    def setUp(self):

        self.host_log_dir = tempfile.mkdtemp(prefix='host_log_dir.')
        self.volume = tempfile.mkdtemp(prefix='volume.')
        for logf in ['test1.log', 'test2.log']:
            with open(os.path.join(self.volume, logf), 'w') as logp:
                logp.write(logf)

    def tearDown(self):
        shutil.rmtree(self.volume)
        shutil.rmtree(self.host_log_dir)

    def test_get_logfiles_list(self, *args):

        inspect = {
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
            "Mounts": [
                    {
                        "Source": self.volume,
                        "Destination": "/data"
                    }
            ],
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


        self.docker_container = crawler.dockercontainer.\
            DockerContainer(inspect['Id'], inspect)

        self.docker_container._get_container_log_files = get_container_log_files
        self.docker_container.log_file_list = [
            {'name': '/data/test1.log', 'type': None}]


        log_list = self.docker_container._set_logfiles_links_source_and_dest(
            {'logcrawler':{'host_log_basedir':self.host_log_dir}})
        log_list = self.docker_container.logs_list
        for log_dict in log_list:
            if log_dict['name'] == '/data/test1.log':
                self.assertEqual(
                    log_dict['dest'], self.host_log_dir + '/data/test1.log')
                self.assertEqual(log_dict['source'],
                                 self.volume + '/test1.log')

if __name__ == '__main__':
    logging.basicConfig(filename='test_dockerutils.log', filemode='a',
                        format='%(asctime)s %(levelname)s : %(message)s', level=logging.DEBUG)

    unittest.main()
