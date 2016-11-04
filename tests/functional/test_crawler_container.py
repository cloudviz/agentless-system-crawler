import unittest
import docker
import requests.exceptions
import tempfile
import os
import shutil
import subprocess
import sys

# Tests for crawlers in kraken crawlers configuration.

import crawler.crawlutils

import logging

# Tests conducted with a single container running.


class SingleContainerTests(unittest.TestCase):

    def setUp(self):
        root = logging.getLogger()
        root.setLevel(logging.DEBUG)
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        root.addHandler(ch)

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

        self.docker.pull(repository='ubuntu', tag='latest')
        self.container = self.docker.create_container(
            image='ubuntu:latest', command='/bin/sleep 60')
        self.tempd = tempfile.mkdtemp(prefix='crawlertest.')
        self.docker.start(container=self.container['Id'])

    def tearDown(self):
        self.docker.stop(container=self.container['Id'])
        self.docker.remove_container(container=self.container['Id'])

        shutil.rmtree(self.tempd)

    def testCrawlContainer1(self):
        os.makedirs(self.tempd + '/out')

        # Adding every single option (even if not used in this test), to make
        # writing other tests easier
        options = {
            'features': ['cpu', 'memory', 'interface', 'package'],
            'format': 'graphite',
            'crawlmode': 'OUTCONTAINER',
            'urls': [
                'file://' + self.tempd + '/out/crawler'],
            'options': {
                'load': {},
                'process': {},
                'metric': {},
                'logcrawler': {
                    'log_types_file':
                        'd464347c-3b99-11e5-b0e9-062dcffc249f.type-mapping',
                    'host_log_basedir': '/var/log/crawler_container_logs/',
                    'default_log_files': [
                        {
                            'type': None,
                            'name': '/var/log/messages'},
                        {
                            'type': None,
                            'name': '/etc/csf_env.properties'}]},
                'file': {
                    'avoid_setns': False,
                    'exclude_dirs': [
                        'boot',
                        'dev',
                        'proc',
                        'sys',
                        'mnt',
                        'tmp',
                        'var/cache',
                        'usr/share/man',
                        'usr/share/doc',
                        'usr/share/mime'],
                    'root_dir': '/'},
                'mountpoint': 'Undefined',
                'disk': {},
                'environment': 'cloudsight',
                'memory': {},
                'config': {
                    'avoid_setns': False,
                    'exclude_dirs': [
                        'dev',
                        'proc',
                        'mnt',
                        'tmp',
                        'var/cache',
                        'usr/share/man',
                        'usr/share/doc',
                        'usr/share/mime'],
                    'root_dir': '/',
                    'discover_config_files': True,
                    'known_config_files': [
                        'etc/passwd',
                        'etc/group',
                        'etc/hosts',
                        'etc/hostname',
                        'etc/mtab',
                        'etc/fstab',
                        'etc/aliases',
                        'etc/ssh/ssh_config',
                        'etc/ssh/sshd_config',
                        'etc/sudoers']},
                'metadata': {
                    'extra_metadata': {},
                    'container_long_id_to_namespace_map': {},
                    'extra_metadata_for_all': False},
                'dockerhistory': {},
                'compress': False,
                'interface': {},
                '_test_crash': {},
                'package': {
                    'avoid_setns': False},
                'docker_containers_list': 'ALL',
                'partition_strategy': {
                    'args': {
                        'process_id': 0,
                        'num_processes': 1},
                    'name': 'equally_by_pid'},
                'connection': {},
                '_test_infinite_loop': {},
                'dockerinspect': {},
                'dockerps': {},
                'link_container_log_files': False,
                'os': {
                    'avoid_setns': False},
                'cpu': {}}}

        crawler.crawlutils.snapshot(**options)

        subprocess.call(['/bin/chmod', '-R', '777', self.tempd])

        files = os.listdir(self.tempd + '/out')
        assert len(files) == 1

        f = open(self.tempd + '/out/' + files[0], 'r')
        output = f.read()
        print output  # only printed if the test fails
        assert 'interface-lo.if_octets.tx' in output
        assert 'cpu-0.cpu-idle' in output
        assert 'memory.memory-used' in output
        assert 'apt.pkgsize' in output
        f.close()

    def testCrawlContainer2(self):
        env = os.environ.copy()
        mypath = os.path.dirname(os.path.realpath(__file__))
        os.makedirs(self.tempd + '/out')

        # crawler itself needs to be root
        process = subprocess.Popen(
            [
                '/usr/bin/python', mypath + '/../../crawler/crawler.py',
                '--url', 'file://' + self.tempd + '/out/crawler',
                '--features', 'cpu,memory,interface,package',
                '--crawlContainers', 'ALL',
                '--format', 'graphite',
                '--crawlmode', 'OUTCONTAINER',
                '--numprocesses', '1'
            ],
            env=env)
        stdout, stderr = process.communicate()
        assert process.returncode == 0

        print stderr
        print stdout

        subprocess.call(['/bin/chmod', '-R', '777', self.tempd])

        files = os.listdir(self.tempd + '/out')
        assert len(files) == 1

        f = open(self.tempd + '/out/' + files[0], 'r')
        output = f.read()
        print output  # only printed if the test fails
        assert 'interface-lo.if_octets.tx' in output
        assert 'cpu-0.cpu-idle' in output
        assert 'memory.memory-used' in output
        assert 'apt.pkgsize' in output
        f.close()

    def testCrawlContainer3(self):
        env = os.environ.copy()
        mypath = os.path.dirname(os.path.realpath(__file__))
        os.makedirs(self.tempd + '/out')

        # crawler itself needs to be root
        process = subprocess.Popen(
            [
                '/usr/bin/python', mypath + '/../../crawler/crawler.py',
                '--url', 'file://' + self.tempd + '/out/crawler',
                '--features', 'os,process',
                '--crawlContainers', 'ALL',
                '--crawlmode', 'OUTCONTAINER',
                '--numprocesses', '1'
            ],
            env=env)
        stdout, stderr = process.communicate()
        assert process.returncode == 0

        print stderr
        print stdout

        subprocess.call(['/bin/chmod', '-R', '777', self.tempd])

        files = os.listdir(self.tempd + '/out')
        assert len(files) == 1

        f = open(self.tempd + '/out/' + files[0], 'r')
        output = f.read()
        print output  # only printed if the test fails
        assert 'sleep' in output
        assert 'linux' or 'Linux' in output
        f.close()

    def testCrawlContainerAvoidSetns(self):
        os.makedirs(self.tempd + '/out')

        # Adding every single option (even if not used in this test), to make
        # writing other tests easier
        options = {
            'features': ['cpu', 'memory', 'interface', 'package'],
            'format': 'graphite',
            'crawlmode': 'OUTCONTAINER',
            'urls': [
                'file://' + self.tempd + '/out/crawler'],
            'options': {
                'load': {},
                'process': {},
                'metric': {},
                'logcrawler': {
                    'log_types_file':
                        'd464347c-3b99-11e5-b0e9-062dcffc249f.type-mapping',
                    'host_log_basedir': '/var/log/crawler_container_logs/',
                    'default_log_files': [
                        {
                            'type': None,
                            'name': '/var/log/messages'},
                        {
                            'type': None,
                            'name': '/etc/csf_env.properties'}]},
                'file': {
                    'avoid_setns': False,
                    'exclude_dirs': [
                        'boot',
                        'dev',
                        'proc',
                        'sys',
                        'mnt',
                        'tmp',
                        'var/cache',
                        'usr/share/man',
                        'usr/share/doc',
                        'usr/share/mime'],
                    'root_dir': '/'},
                'mountpoint': 'Undefined',
                'disk': {},
                'environment': 'cloudsight',
                'memory': {},
                'config': {
                    'avoid_setns': False,
                    'exclude_dirs': [
                        'dev',
                        'proc',
                        'mnt',
                        'tmp',
                        'var/cache',
                        'usr/share/man',
                        'usr/share/doc',
                        'usr/share/mime'],
                    'root_dir': '/',
                    'discover_config_files': True,
                    'known_config_files': [
                        'etc/passwd',
                        'etc/group',
                        'etc/hosts',
                        'etc/hostname',
                        'etc/mtab',
                        'etc/fstab',
                        'etc/aliases',
                        'etc/ssh/ssh_config',
                        'etc/ssh/sshd_config',
                        'etc/sudoers']},
                'metadata': {
                    'extra_metadata': {},
                    'container_long_id_to_namespace_map': {},
                    'extra_metadata_for_all': False},
                'dockerhistory': {},
                'compress': False,
                'interface': {},
                '_test_crash': {},
                'package': {
                    'avoid_setns': True},
                'docker_containers_list': 'ALL',
                'partition_strategy': {
                    'args': {
                        'process_id': 0,
                        'num_processes': 1},
                    'name': 'equally_by_pid'},
                'connection': {},
                '_test_infinite_loop': {},
                'dockerinspect': {},
                'dockerps': {},
                'link_container_log_files': False,
                'os': {
                    'avoid_setns': False},
                'cpu': {}}}

        crawler.crawlutils.snapshot(**options)

        subprocess.call(['/bin/chmod', '-R', '777', self.tempd])

        files = os.listdir(self.tempd + '/out')
        assert len(files) == 1

        f = open(self.tempd + '/out/' + files[0], 'r')
        output = f.read()
        print output  # only printed if the test fails
        assert 'interface-lo.if_octets.tx' in output
        assert 'cpu-0.cpu-idle' in output
        assert 'memory.memory-used' in output
        assert 'apt.pkgsize' in output
        f.close()


if __name__ == '__main__':
    unittest.main()
