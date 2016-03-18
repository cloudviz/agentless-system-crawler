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

from dockerutils import (
    exec_dockerps,
    get_docker_container_json_logs_path,
    get_docker_container_rootfs_path,
    exec_dockerinspect)

try:
    import alchemy
except ImportError:
    alchemy = None


from crawler_exceptions import ContainerInvalidEnvironment

logger = logging.getLogger('crawlutils')


def list_docker_containers(namespace_opts={}):
    """
    Get the list of running Docker containers, as `DockerContainer` objects.

    This is basically polling. Ideally, we should subscribe to Docker
    events so we can keep the containers list up to date without having to
    poll like this.
    """
    for inspect in exec_dockerps():
        long_id = inspect['Id']
        try:
            yield DockerContainer(long_id, inspect, namespace_opts)
        except ContainerInvalidEnvironment as e:
            logger.exception(e)


class DockerContainer(Container):

    def __init__(
        self,
        long_id,
        inspect=None,
        namespace_opts={},
    ):

        if not inspect:
            inspect = exec_dockerinspect(long_id)

        state = inspect['State']
        self.image = inspect['Image']

        assert(long_id == inspect['Id'])
        self.long_id = long_id
        self.pid = state['Pid']
        self.name = inspect['Name']
        self.running = state['Running']
        self.created = inspect['Created']
        self.network_settings = inspect['NetworkSettings']
        self.cmd = inspect['Config']['Cmd']
        self.inspect = inspect

        # This short ID is mainly used for logging purposes

        self.short_id = long_id[:12]

        # Docker prepends a '/' to the name. Let's remove it.
        if self.name[0] == '/':
            self.name = self.name[1:]

        self.namespace = None

    def is_docker_container(self):
        return True

    # Find the mount point of the specified cgroup

    def get_cgroup_dir(self, dev=''):
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
        return os.path.join(self.get_cgroup_dir('memory'), 'docker',
                            self.long_id, node)

    def get_cpu_cgroup_path(self, node='cpuacct.usage'):
        return os.path.join(self.get_cgroup_dir('cpuacct'), 'docker',
                            self.long_id, node)

    def __str__(self):
        return str(self.__dict__)

    def link_logfiles(self,
                      options=defaults.DEFAULT_CRAWL_OPTIONS):

        host_log_dir = self._get_logfiles_links_dest(
            options['logcrawler']['host_log_basedir'],
            options['environment'],
        )

        logs_list = self._get_logfiles_list(host_log_dir, options)

        logger.debug('Linking log files for container %s' % self.short_id)

        # create an empty dir for the container logs

        if not os.path.exists(host_log_dir):
            os.makedirs(host_log_dir)

        # Create a symlink from src to dst

        for log in logs_list:
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
                             for log in logs_list]
                json.dump(logs_dict, outfile)
        except (OSError, IOError) as e:
            # Not a critical error: move on
            logger.exception(e)

    def unlink_logfiles(self,
                        options=defaults.DEFAULT_CRAWL_OPTIONS):

        host_log_basedir = options['logcrawler']['host_log_basedir']
        host_log_dir = self._get_logfiles_links_dest(
            host_log_basedir,
            options['environment'],
        )

        logger.info('Un-linking log files for container %s.'
                    % self.short_id)

        try:
            shutil.rmtree('/tmp/' + self.namespace)
        except (IOError, OSError) as e:
            pass
        try:
            shutil.move(host_log_dir, '/tmp/' + self.namespace)
        except (IOError, OSError) as e:
            logger.exception(e)
            pass

    def _log_locations_json_sanity_check(self, data):
        """Check the sanity of the user log locations json.

        This json can have anything in it. Just make sure it is a valid json,
        and it has all the fields we need. Also check that it's not too big and
        the number of logfiles is decent.
        """
        max_data_len = 1e6  # one MB looks excesive
        max_files = 100  # more than 100 log files to link is excessive

        if len(data) > max_data_len:
            raise KeyError('The file list is too large.')

        if 'log_files' not in data:
            raise KeyError('log_files key missing.')

        if len(data.keys()) > 1:
            raise KeyError('The only valid key is log_files.')

        log_files = data['log_files']

        if len(log_files) > max_files:
            raise KeyError('Too many log files (> 1000).')

        for log in log_files:
            if 'name' not in log.keys():
                raise KeyError('Missing the name key.')

            if len(log.keys()) > 2:
                raise KeyError('Too many keys in the log tuple.')

            if len(log.keys()) > 1 and 'type' not in log.keys():
                raise KeyError('Only other valid key is type.')

            if not isinstance(log['name'], str):
                raise KeyError('name value is not a string.')

            if 'type' in log and not isinstance(log['type'], str):
                raise KeyError('type value is not a string.')

    def _parse_log_locations(
        self,
        json_path=None,
        var=None,
        is_var=True,
        isJson=True,
    ):
        """
        TODO

        The user can provide a list of logfiles in a container for us
        to maintain links to.
        """

        container = self
        logs = []  # list of maps {name:name,type:type}
        data = None
        try:
            if is_var:
                data = misc.GetProcessEnv(container.pid)[var]
            else:
                with open(json_path, 'r') as fp:
                    data = fp.read()
            if isJson:

                # remove double quotes around json

                if data.startswith('"'):
                    data = data[1:]
                if data.endswith('"'):
                    data = data[:-1]

                # json doesn't allow single quotes

                data = data.replace("'", '"')
                data = json.loads(data)
                self._log_locations_json_sanity_check(data)
                logs.extend(data['log_files'])
            else:
                log_locations = data.split(',')
                logs = [{'name': name.strip(), 'type': None}
                        for name in log_locations]
        except (KeyError, ValueError) as e:
            logger.debug('There is a problem with the env. variables: %s' % e)
        except (IOError, OSError) as e:
            logger.debug(e)
        return logs

    def _get_container_log_files(self, rootfs_path,
                                 options=defaults.DEFAULT_CRAWL_OPTIONS,
                                 ):
        """
        Returns a list of path strings, one for each logfile we should maintain
        symlinks for.

        The paths are relative to the filesystem of the container. For example
        the path for /var/log/messages in the container will be just
        /var/log/messages in this list.

        Security consideration. We make sure that the path is absolute and it
        does not contain any '..' in it.
        """
        # List of maps {name:name,type:type}
        #container_logs = options['logcrawler']['default_log_files']

        # following files need to be ported to envionment modules
        # cloudsight, watson, alchemy etc.
        logs = self._parse_log_locations(
            var='LOG_LOCATIONS',
            isJson=False)
        self.log_file_list.extend(logs)

        logs = self._parse_log_locations(
            var='LOGS_CONFIG',
            isJson=True)
        self.log_file_list.extend(logs)

        # Finally, make sure that the paths are absolute

        for log in self.log_file_list:
            name = log['name']
            if not os.path.isabs(name) or '..' in name:
                self.log_file_list.remove(log)
                logger.warning(
                    'User provided a log file path that is not absolute: %s' %
                    name)
        return self.log_file_list

    def _get_logfiles_list(self,
                           host_log_dir,
                           options=defaults.DEFAULT_CRAWL_OPTIONS):
        """
        Returns list of log files as a list of dictionaries `{name, type,
        source, dest}` to be linked to `host_log_dir`.
        """

        # Get the rootfs of the container in the host

        rootfs_path = get_docker_container_rootfs_path(
            self.long_id, self.inspect)

        logs_list = []

        self._get_container_log_files(rootfs_path, options)

        for logdict in self.log_file_list:
            name = logdict['name']
            _type = logdict['type']
            log_source = rootfs_path + name
            log_dest = host_log_dir + name
            log = {
                'name': name,
                'type': _type,
                'source': log_source,
                'dest': log_dest}
            if log not in logs_list:
                logs_list.append(log)

        docker_log_source = get_docker_container_json_logs_path(
            self.long_id, self.inspect)
        name = 'docker.log'
        docker_log_dest = os.path.join(host_log_dir, name)
        logs_list.append({'name': name,
                          'type': None,
                          'source': docker_log_source,
                          'dest': docker_log_dest})

        return logs_list

    def _get_logfiles_links_dest(
        self,
        host_log_basedir,
        environment='cloudsight',
    ):
        """
        Returns the path in the host file system where the container's log
        files should be linked to.

        This string depends on the environment. For the `cloudsight`
        environment, this will look like this:
        `'/var/log/crawler_container_logs/127.0.0.1/my_container/'`
        """
        return os.path.join(host_log_basedir, self.log_prefix)
