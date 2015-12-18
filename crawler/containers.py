#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import logging
import subprocess
import shutil

# External dependencies that must be easy_install'ed separately

import simplejson as json
import psutil

import defaults
from dockerutils import (get_docker_container_logs_path,
                         get_docker_container_rootfs_path,
                         list_docker_containers)
from container import Container
import misc

try:
    import alchemy
except ImportError:
    alchemy = None

logger = logging.getLogger('crawlutils')


def get_pid_namespace(pid):
    try:
        ns = os.stat('/proc/' + str(pid) + '/ns/pid').st_ino
        return ns
    except Exception:
        logger.debug('There is no container with pid=%s running.'
                     % pid)
        return None


def process_is_crawler(proc):
    try:
        cmdline = (proc.cmdline() if hasattr(proc.cmdline, '__call__'
                                             ) else proc.cmdline)

        # curr is the crawler process

        curr = psutil.Process(os.getpid())
        curr_cmdline = (
            curr.cmdline() if hasattr(
                curr.cmdline,
                '__call__') else curr.cmdline)
        if cmdline == curr_cmdline:
            return True
    except:
        pass
    return False


def list_all_containers(user_list='ALL'):

    all_docker_containers = list_docker_containers()

    if user_list in ['ALL', 'all', 'All']:
        init_ns = get_pid_namespace(1)

        visited_ns = set()  # visited PID namespaces

        # Start with all docker containers

        for container in all_docker_containers:
            curr_ns = get_pid_namespace(container.pid)
            if not curr_ns:
                continue
            if curr_ns not in visited_ns and curr_ns != init_ns:
                visited_ns.add(curr_ns)
                yield container

        # Continue with all other containers not known to docker

        for p in psutil.process_iter():
            pid = (p.pid() if hasattr(p.pid, '__call__') else p.pid)
            if process_is_crawler(p):

                # don't confuse the crawler process with a container

                continue
            curr_ns = get_pid_namespace(pid)
            if not curr_ns:

                # invalid container

                continue
            if curr_ns not in visited_ns and curr_ns != init_ns:
                visited_ns.add(curr_ns)
                yield Container(pid)
    else:

        # User provided a list of containers

        user_containers = user_list.split(',')
        for container in all_docker_containers:
            short_id_match = container.short_id in user_containers
            long_id_match = container.long_id in user_containers
            if short_id_match or long_id_match:
                yield container


# XXX rename to sanity_check_log_locations_json
def SanityCheckLogLocationsJson(data):
    """Check the sanity of the user log locations json.

    This json can have anything in it. Just make sure it it is a valid json,
    and it has all the fields we need. Also check that it's not too big and
    the number of logfiles is decent.
    """

    try:
        max_data_len = 1e6  # one MB looks excesive
        max_files = 1000
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
    except Exception:
        raise KeyError('Not a valid {} json.')


def ParseLogLocations(
    container=None,
    json_path=None,
    var=None,
    is_var=True,
    isJson=True,
):
    log_locations_types = []  # list of maps {name:name,type:type}
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
            SanityCheckLogLocationsJson(data)
            log_locations_types.extend(data['log_files'])
        else:
            log_locations = data.split(',')
            log_locations_types = [{'name': name.strip(), 'type': None}
                                   for name in log_locations]
    except json.JSONDecodeError as exc:
        logger.warning(
            'The container log file list %s is not a valid json file.' %
            data)
        pass
    except KeyError as exc:
        if is_var and not data:
            logger.debug(
                'There is no %s env. variable or there is no.log_files entry '
                'in the json file.' % var)
        else:
            logger.warning('Container %s does not have a valid json file: %s'
                           % (container.namespace, str(data)))
        pass
    except IOError as exc:
        logger.debug(exc)
        pass
    except OSError as exc:
        logger.exception(exc)
        pass
    except Exception as e:
        logger.exception(e)
        raise
    return log_locations_types


def get_container_log_files(container, rootfs_path,
                            container_logs_file='/etc/logcrawl-logs.json'
                            ):
    container_logs = []  # list of maps {name:name,type:type}
    log_locations_types = []  # list of maps {name:name,type:type}

    logs = ParseLogLocations(
        container=container,
        var='LOG_LOCATIONS',
        is_var=True,
        isJson=False)
    container_logs.extend(logs)
    logs = ParseLogLocations(
        container=container,
        var='LOGS_CONFIG',
        is_var=True,
        isJson=True)
    container_logs.extend(logs)
    json_path = rootfs_path + container_logs_file
    logs = ParseLogLocations(
        container=container,
        json_path=json_path,
        is_var=False,
        isJson=True)
    container_logs.extend(logs)

    # Finally, make sure that the paths are absolute

    for log in log_locations_types:
        name = log['name']
        if os.path.isabs(name) and '..' not in name:
            container_logs.append(log)
        else:
            logger.warning(
                'User provided a log file path that is not absolute: %s' %
                name)
    return container_logs


def get_container_logs_dir(
    ctr_namespace,
    pid,
    short_id,
    long_id,
    host_log_basedir,
    env='cloudsight',
):
    if env == 'cloudsight':
        host_log_dir = os.path.join(host_log_basedir, ctr_namespace)
        return host_log_dir
    elif env == 'alchemy':
        if pid == '1':
            logger.info(
                'get_container_logs_dir returning None for pid=1 as we do not '
                'want to crawl the host.')
            return None
        if not long_id:
            logger.info(
                'Not crawling container with pid %s because it does not seem '
                'to be a docker container.' % pid)
            return None
        else:
            if alchemy is None:
                raise ImportError("Please setup alchemy.py correctly.")
            # XXX move docker specific stuff somewhere else
            host_dir = alchemy.get_logs_dir_on_host(long_id, 'docker')
            if not host_dir:
                logger.info('Container %s does not have alchemy metadata.'
                            % short_id)
            host_log_dir = os.path.join(host_log_basedir, host_dir)
            return host_log_dir
    else:
        logger.error('Unknown environment %s' % env)
        return None


container_log_links_cache = dict()


def do_link_container_log_files(container_list, env='cloudsight',
                                options=defaults.DEFAULT_CRAWL_OPTIONS):
    global container_log_links_cache

    ftype = 'logcrawler'
    fopts = options.get(ftype, defaults.DEFAULT_CRAWL_OPTIONS.get(ftype, None))
    default_log_files = fopts.get('default_log_files', [])
    host_log_basedir = fopts.get('host_log_basedir',
                                 '/var/log/crawler_container_logs/')
    container_logs_list_file = fopts.get('container_logs_list_file',
                                         '/etc/logcrawl-logs.json')
    log_types_file = fopts.get(
        'log_types_file',
        'd464347c-3b99-11e5-b0e9-062dcffc249f.type-mapping')

    # Remove dead containers log links

    for container in container_log_links_cache.values():
        if container not in container_list:
            del container_log_links_cache[container.short_id]
            logger.info('Un-linking log files for container %s.'
                        % container.namespace)

            host_log_dir = get_container_logs_dir(
                container.namespace,
                container.pid,
                container.short_id,
                container.long_id,
                host_log_basedir,
                env,
            )
            try:
                shutil.rmtree('/tmp/' + container.namespace)
            except Exception as e:
                pass
            try:
                shutil.move(host_log_dir, '/tmp/' + container.namespace)
            except Exception as e:
                logger.exception(e)
                pass

    for container in container_list:
        if container.short_id in container_log_links_cache:
            logger.debug('Logs for container %s already linked.'
                         % container.short_id)

            # continue

        host_log_dir = get_container_logs_dir(
            container.namespace,
            container.pid,
            container.short_id,
            container.long_id,
            host_log_basedir,
            env,
        )
        if not host_log_dir:
            logger.warning(
                'Not linking log files for container ' +
                container.short_id)
            continue

        logger.debug('Linking log files for container %s' % container.short_id)

        # create an empty dir for the container logs

        proc = subprocess.Popen('mkdir -p ' + host_log_dir, shell=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        _ = proc.stdout.read()

        if container.isDockerContainer():
            try:
                docker_log_path = \
                    get_docker_container_logs_path(container.long_id)
                docker_host_log_path = os.path.join(host_log_dir,
                                                    'docker.log')
                os.symlink(docker_log_path, docker_host_log_path)
                logger.info('Linking container %s docker logfile %s -> %s'
                            % (container.short_id, docker_log_path,
                                docker_host_log_path))
            except OSError as e:
                logger.debug('Link already exists: %s -> %s'
                             % (docker_log_path, docker_host_log_path))
                pass
            except Exception as e:
                logger.debug(e)

                # We can live without having the docker logs linked

                pass

        # Get the rootfs of the container in the host

        rootfs_path = get_docker_container_rootfs_path(container)

        # Generate the container_logs_list

        container_logs_list = get_container_log_files(container, rootfs_path,
                                                      container_logs_list_file)
        container_logs_list.extend(default_log_files)  # add default ones

        # Write the list (and the types) to a known file for logstash
        # to get it and use to apply plugins.

        try:
            types_host_log_path = os.path.join(host_log_dir,
                                               log_types_file)
            with open(types_host_log_path, 'w') as outfile:
                json.dump(container_logs_list, outfile, indent=4,
                          separators=(',', ': '))
        except Exception as e:
            logger.exception(e)
            pass

        # Finally, link the log files

        for log in container_logs_list:
            logfile = log['name']
            src = rootfs_path + logfile
            if not os.path.exists(src):
                logger.debug(
                    'Log file %s does not exist, but linking it anyway' %
                    src)
            host_log_path = host_log_dir + logfile
            try:

                # create the same directory structure

                proc = subprocess.Popen(
                    'mkdir -p ' +
                    os.path.dirname(host_log_path),
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE)
                _ = proc.stdout.read()
                os.symlink(src, host_log_path)
                logger.info('Linking container %s logfile %s -> %s'
                            % (container.short_id, src, host_log_path))
            except IOError as exc:
                logger.exception(exc)
                pass
            except OSError as exc:
                logger.debug('Link already exists: %s -> %s' % (src,
                                                                host_log_path))
                pass
            except Exception as e:
                logger.exception(exc)
                raise
            if container.short_id not in container_log_links_cache:
                container_log_links_cache[container.short_id] = container


def new_urls_for_container(
    urls,
    short_id,
    pid,
    snapshot_num,
):
    for u in urls:
        if u.startswith('file:'):
            if not short_id:
                file_suffix = '{0}.{1}'.format(pid, snapshot_num)
            else:
                file_suffix = '{0}.{1}'.format(short_id, snapshot_num)
            yield '{0}.{1}'.format(u, file_suffix)
        else:
            yield u


def get_ctr_namespace(
    namespace,
    container,
    env='cloudsight',
    container_long_id_to_namespace_map={},
):
    if container.long_id in container_long_id_to_namespace_map:
        return container_long_id_to_namespace_map[container.long_id]

    if env == 'cloudsight':
        if container.pid != '1':
            if not container.short_id:
                namespace += '/' + container.pid
            else:
                name = (
                    container.name if len(
                        container.name) > 0 else container.short_id)
                name = (name[1:] if name[0] == '/' else name)
                namespace += '/' + name
        return namespace
    elif env == 'alchemy':
        if container.pid == '1':
            logger.info(
                'get_ctr_namespace() returning None for pid=1 as we do not '
                'want to crawl the host.')
            return None
        if not container.isDockerContainer():
            logger.info(
                'Not crawling container with pid %s because it does not seem '
                'to be a docker container.' % container.pid)
            return None
        else:
            if alchemy is None:
                raise ImportError("Please setup alchemy.py correctly.")
            namespace = alchemy.get_namespace(container.long_id, 'docker')
            logger.info('crawling %s' % namespace)
            if not namespace:
                logger.info('Container %s does not have alchemy metadata.'
                            % container.short_id)
            return namespace
    else:
        logger.error('Unknown environment %s' % env)
        return None


def get_filtered_list_of_containers(
    user_list,
    partition_strategy=defaults.DEFAULT_PARTITION_STRATEGY,
):
    assert(partition_strategy['name'] == 'equally_by_pid')
    process_id = partition_strategy['args']['process_id']
    num_processes = partition_strategy['args']['num_processes']

    filtered_list = []
    containers_list = list_all_containers(user_list)
    for container in containers_list:

        # The partition strategy is to split all the containers equally by
        # process pid. We do it by hashing the long_id of the container.

        _hash = container.long_id
        num = int(_hash, 16) % int(num_processes)
        if num == process_id:
            filtered_list.append(container)

    return filtered_list
