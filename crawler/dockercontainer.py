#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import subprocess
import logging
import shutil

from container import Container
import misc
import defaults
import json
import glob
from dockerutils import (exec_dockerps,
                         get_docker_container_json_logs_path,
                         get_docker_container_rootfs_path,
                         exec_dockerinspect)
import plugins_manager
from crawler_exceptions import (ContainerInvalidEnvironment,
                                ContainerNonExistent,
                                DockerutilsNoJsonLog)
from requests.exceptions import HTTPError

logger = logging.getLogger('crawlutils')


def list_docker_containers(container_opts={}):
    """
    Get the list of running Docker containers, as `DockerContainer` objects.

    This is basically polling. Ideally, we should subscribe to Docker
    events so we can keep the containers list up to date without having to
    poll like this.
    """
    for inspect in exec_dockerps():
        long_id = inspect['Id']
        try:
            c = DockerContainer(long_id, inspect, container_opts)
            if c.namespace:
                yield c
        except ContainerInvalidEnvironment as e:
            logger.exception(e)


class DockerContainer(Container):

    DOCKER_LOG_FILE = "docker.log"

    def __init__(
        self,
        long_id,
        inspect=None,
        container_opts={},
    ):

        if not inspect:
            try:
                inspect = exec_dockerinspect(long_id)
            except HTTPError:
                raise ContainerNonExistent('No docker container with ID: %s'
                                           % long_id)

        state = inspect['State']
        self.image = inspect['Image']

        assert(long_id == inspect['Id'])
        self.long_id = long_id
        self.pid = str(state['Pid'])
        self.name = inspect['Name']
        self.running = state['Running']
        self.created = inspect['Created']
        self.network_settings = inspect['NetworkSettings']
        self.cmd = inspect['Config']['Cmd']
        self.mounts = inspect.get('Mounts')
        self.volumes = inspect.get('Volumes')
        self.inspect = inspect

        # This short ID is mainly used for logging purposes
        self.short_id = long_id[:12]

        # Docker prepends a '/' to the name. Let's remove it.
        if self.name[0] == '/':
            self.name = self.name[1:]

        repo_tag = inspect.get('RepoTag', '')
        self.docker_image_long_name = repo_tag
        self.docker_image_short_name = os.path.basename(repo_tag)
        if ':' in repo_tag and not '/' in repo_tag.rsplit(':', 1)[1]:
            self.docker_image_tag = repo_tag.rsplit(':', 1)[1]
        else:
            self.docker_image_tag = ''
        self.docker_image_registry = os.path.dirname(repo_tag).split('/')[0]
        try:
            # This is the 'abc' in 'registry/abc/bla:latest'
            self.owner_namespace = os.path.dirname(repo_tag).split('/', 1)[1]
        except IndexError:
            self.owner_namespace = ''

        self._set_mounts_list()

        try:
            self.root_fs = get_docker_container_rootfs_path(self.long_id)
        except HTTPError as e:
            logger.exception(e)
            self.root_fs = None

        self._set_logfiles_links_source()
        self._set_environment_specific_options(container_opts)
        self._set_logfiles_links_source_and_dest()

    def is_docker_container(self):
        return True

    def _set_environment_specific_options(self,
                                          container_opts={}):
        """
        This function is used to setup these fields: namespace, log_prefix, and
        logfiles_links_source.
        """

        logger.info('setup_namespace_and_metadata: long_id=' +
                    self.long_id)

        _map = container_opts.get('long_id_to_namespace_map', {})
        if self.long_id in _map:
            self.namespace = _map[self.long_id]
            self.log_prefix = ''
            self.logfiles_links_source = []
            return

        host_namespace = container_opts.get('host_namespace', 'undefined')
        options = defaults.DEFAULT_CRAWL_OPTIONS
        default_logs = options['logcrawler']['default_log_files']

        try:
            _options = {'root_fs': self.root_fs, 'type': 'docker',
                        'name': self.name, 'host_namespace': host_namespace,
                        'container_logs': default_logs}
            runtime_env = plugins_manager.get_runtime_env_plugin()
            namespace = runtime_env.get_container_namespace(
                self.long_id, _options)
            if not namespace:
                _env = runtime_env.get_environment_name()
                logger.warning('Container %s does not have %s '
                               'metadata.' % (self.short_id, _env))
                raise ContainerInvalidEnvironment('')
            self.namespace = namespace

            self.log_prefix = runtime_env.get_container_log_prefix(
                self.long_id, _options)

            self.logfiles_links_source.extend(runtime_env.get_container_log_file_list(
                self.long_id, _options))
        except ValueError:
            # XXX-kollerr: plugins are not supposed to throw ValueError
            logger.warning('Container %s does not have a valid alchemy '
                           'metadata json file.' % self.short_id)
            raise ContainerInvalidEnvironment()

    def _set_mounts_list(self):
        """
        Create self.mounts out of Volumes for old versions of Docker
        """

        if not self.mounts and self.volumes:
            self.mounts = [{'Destination': vol,
                            'Source': self.volumes[vol]}
                           for vol in self.volumes]
        elif not self.mounts and not self.volumes:
            self.mounts = []

    # Find the mount point of the specified cgroup

    def _get_cgroup_dir(self, dev=''):
        paths = [os.path.join('/cgroup/', dev),
                 os.path.join('/sys/fs/cgroup/', dev)]
        for path in paths:
            if os.path.ismount(path):
                return path

        # Try getting the mount point from /proc/mounts
        try:
            # XXX don't start a process just for this
            proc = subprocess.Popen(
                'grep "cgroup/' +
                dev +
                ' " /proc/mounts | awk \'{print $2}\'',
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            return proc.stdout.read().strip()
        except Exception as e:
            raise e

    def get_memory_cgroup_path(self, node='memory.stat'):
        return os.path.join(self._get_cgroup_dir('memory'), 'docker',
                            self.long_id, node)

    def get_cpu_cgroup_path(self, node='cpuacct.usage'):
        # In kernels 4.x, the node is actually called 'cpu,cpuacct'
        cgroup_dir = (self._get_cgroup_dir('cpuacct') or
                      self._get_cgroup_dir('cpu,cpuacct'))
        return os.path.join(cgroup_dir, 'docker', self.long_id, node)

    def __str__(self):
        return str(self.__dict__)

    def link_logfiles(self,
                      options=defaults.DEFAULT_CRAWL_OPTIONS):

        host_log_dir = self._get_logfiles_links_dest(
            options['logcrawler']['host_log_basedir']
        )

        logger.debug('Linking log files for container %s' % self.short_id)

        # create an empty dir for the container logs

        if not os.path.exists(host_log_dir):
            os.makedirs(host_log_dir)

        # Create a symlink from src to dst

        for log in self.logs_list:
            try:
                if not os.path.exists(log['source']):
                    logger.debug(
                        'Log file %s does not exist, but linking it anyway'
                        % log['source'])
                dest_dir = os.path.dirname(log['dest'])
                if not os.path.exists(dest_dir):
                    os.makedirs(dest_dir)
                os.symlink(log['source'], log['dest'])
                logger.info(
                    'Linking container %s %s logfile %s -> %s' %
                    (self.short_id, log['name'], log['source'], log['dest']))
            except (OSError, IOError) as e:
                logger.debug(e)
                logger.debug('Link already exists: %s -> %s'
                             % (log['source'], log['dest']))
            except Exception as e:
                logger.warning(e)

        # Keep record of what is linked in a file.

        try:
            log_types_file = options['logcrawler']['log_types_file']
            types_host_log_path = os.path.join(host_log_dir,
                                               log_types_file)
            with open(types_host_log_path, 'w') as outfile:
                logs_dict = [{'name': log['name'], 'type': log['type']}
                             for log in self.logs_list]
                json.dump(logs_dict, outfile)
        except (OSError, IOError) as e:
            # Not a critical error: move on
            logger.exception(e)

    def unlink_logfiles(self,
                        options=defaults.DEFAULT_CRAWL_OPTIONS):

        host_log_dir = self._get_logfiles_links_dest(
            options['logcrawler']['host_log_basedir']
        )

        logger.info('Un-linking log files for container %s.'
                    % self.short_id)

        logger.info('Trying to delete this directory and its symlinks: %s.'
                    % host_log_dir)
        assert(host_log_dir.startswith('/var/log/crawler_container_logs/'))

        try:
            shutil.rmtree(host_log_dir)
        except (IOError, OSError) as e:
            logger.error('Could not delete directory: %s' % host_log_dir)
            pass

    def _parse_log_locations(self, var=None):
        """
        TODO

        The user can provide a list of logfiles in a container for us
        to maintain links to.
        """

        container = self
        logs = []  # list of maps {name:name,type:type}
        try:
            logs = [{'name': name.strip(), 'type': None} for name in
                    misc.GetProcessEnv(container.pid)[var].split(',')]
        except (KeyError, ValueError) as e:
            logger.debug('There is a problem with the env. variables: %s' % e)
        return logs

    def _set_logfiles_links_source(self):
        """
        Sets the list of container logs that we should maintain links for.

        The paths are relative to the filesystem of the container. For example
        the path for /var/log/messages in the container will be just
        /var/log/messages in this list.
        """

        self.logfiles_links_source = []

        # following files need to be ported to envionment modules
        # cloudsight, watson, alchemy etc.
        logs = self._parse_log_locations(var='LOG_LOCATIONS')
        self.logfiles_links_source.extend(logs)

    def _set_logfiles_links_source_and_dest(self,
                                            options=defaults.DEFAULT_CRAWL_OPTIONS):
        """
        Returns list of log files as a list of dictionaries `{name, type,
        source, dest}` to be linked to `host_log_dir`.
        """

        host_log_dir = self._get_logfiles_links_dest(
            options['logcrawler']['host_log_basedir']
        )

        logs_list = []

        rootfs_path = self.root_fs
        if not rootfs_path:
            logger.warning(
                'Container %s does not have a rootfs_path set' %
                self.short_id)
            self.logs_list = []
            return

        # First, make sure that the paths are absolute

        for logdict in self.logfiles_links_source:
            name = logdict['name']
            if not os.path.isabs(name) or '..' in name:
                logger.warning(
                    'User provided a log file path that is not absolute: %s' %
                    name)
                continue

            name = logdict['name']
            _type = logdict['type']

            # assuming mount source or destination does not contain '*'
            if not self.mounts:
                lname = rootfs_path + name
                if "*" in lname:
                    src_dest = [(s, s.split(rootfs_path, 1)[1])
                                for s in glob.glob(lname)]
                else:
                    src_dest = [(lname, name)]

            for mount in self.mounts:
                if name.startswith(mount['Destination']):
                    lname = name.replace(mount['Destination'], mount['Source'])
                    if "*" in lname:
                        src_dest = [(s, s.replace(mount['Source'], mount[
                                     'Destination'])) for s in glob.glob(lname)]
                    else:
                        src_dest = [(lname, name)]
                else:
                    lname = rootfs_path + name
                    if "*" in lname:
                        src_dest = [(s, s.split(rootfs_path, 1)[1])
                                    for s in glob.glob(lname)]
                    else:
                        src_dest = [(lname, name)]

            for log_src, log_dest in src_dest:
                log_dest = host_log_dir + log_dest
                log = {
                    'name': name,
                    'type': _type,
                    'source': log_src,
                    'dest': log_dest}

                if log not in logs_list:
                    logs_list.append(log)

        logger.debug('logmap %s' % logs_list)

        try:
            docker_log_source = get_docker_container_json_logs_path(
                self.long_id, self.inspect)
            docker_log_dest = os.path.join(host_log_dir, self.DOCKER_LOG_FILE)
            logs_list.append({'name': self.DOCKER_LOG_FILE,
                              'type': None,
                              'source': docker_log_source,
                              'dest': docker_log_dest})
        except DockerutilsNoJsonLog as e:
            logger.exception(e)

        self.logs_list = logs_list

    def _get_logfiles_links_dest(
        self,
        host_log_basedir
    ):
        """
        Returns the path in the host file system where the container's log
        files should be linked to.
        """

        return os.path.join(host_log_basedir, self.log_prefix)
