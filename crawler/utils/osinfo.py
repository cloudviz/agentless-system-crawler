import os
import re

LSB_RELEASE = 'etc/lsb-release'
OS_RELEASE = 'etc/os-release'
USR_OS_RELEASE = 'usr/lib/os-release'
APT_SOURCES = 'etc/apt/sources.list'
REDHAT_RELEASE = 'etc/redhat-release'
CENTOS_RELEASE = 'etc/centos-release'
SYSTEM_RELEASE = 'etc/system-release'

REDHAT_RE = re.compile(r'red hat enterprise linux .* release (\d+(\.\d)?).*')
CENTOS_RE = re.compile(r'centos (?:linux )?release (\d+(\.\d)?).*')


def _get_file_name(mount_point, filename):
    if mount_point:
        return os.path.join(mount_point, filename)
    return os.path.join('/', filename)


def parse_lsb_release(data):
    result = {}
    for line in data:
        if line.startswith('DISTRIB_ID'):
            result['os'] = line.strip().split('=')[1].lower()
        if line.startswith('DISTRIB_RELEASE'):
            result['version'] = line.strip().split('=')[1].lower()
    return result


def parse_os_release(data):
    result = {}
    for line in data:
        if line.startswith('ID='):
            result['os'] = line.strip().split('=')[1].lower().strip('"')
        if line.startswith('VERSION_ID'):
            result['version'] = line.strip().split('=')[1].lower().strip('"')
    return result


def parse_redhat_release(data):
    result = {}
    for line in data:
        match = REDHAT_RE.match(line.lower())
        if match:
            result['os'] = 'rhel'
            result['version'] = match.group(1)
    return result


def parse_centos_release(data):
    result = {}
    for line in data:
        match = CENTOS_RE.match(line.lower())
        if match:
            result['os'] = 'centos'
            result['version'] = match.group(1)
    return result


def parse_redhat_centos_release(data):
    for line in data:
        if 'centos' in line.lower():
            return parse_centos_release(data)
        elif 'red hat' in line.lower():
            return parse_redhat_release(data)
    return {}


def get_osinfo_from_redhat_centos(mount_point='/'):

    try:
        with open(_get_file_name(mount_point, CENTOS_RELEASE), 'r') as lsbp:
            return parse_redhat_centos_release(lsbp.readlines())
    except IOError:
        try:
            with open(_get_file_name(mount_point,
                                     REDHAT_RELEASE), 'r') as lsbp:
                return parse_redhat_centos_release(lsbp.readlines())
        except IOError:
            try:
                with open(_get_file_name(mount_point,
                                         SYSTEM_RELEASE), 'r') as lsbp:
                    return parse_redhat_centos_release(lsbp.readlines())
            except IOError:
                return {}


def get_osinfo_from_lsb_release(mount_point='/'):
    try:
        with open(_get_file_name(mount_point, LSB_RELEASE), 'r') as lsbp:
            return parse_lsb_release(lsbp.readlines())
    except IOError:
        return {}


def get_osinfo_from_os_release(mount_point='/'):
    try:
        with open(_get_file_name(mount_point, OS_RELEASE), 'r') as lsbp:
            return parse_os_release(lsbp.readlines())
    except IOError:
        try:
            with open(USR_OS_RELEASE, 'r') as lsbp:
                return parse_os_release(lsbp.readlines())
        except IOError:
            return {}


def get_osinfo(mount_point='/'):

    result = get_osinfo_from_lsb_release(mount_point)
    if result:
        return result

    result = get_osinfo_from_os_release(mount_point)
    if result:
        return result

    return get_osinfo_from_redhat_centos(mount_point)
