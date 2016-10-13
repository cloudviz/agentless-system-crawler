import os
from package_utils import get_rpm_packages, get_dpkg_packages
from crawler_exceptions import (CrawlError,
                                CrawlUnsupportedPackageManager)
import logging
import osinfo

logger = logging.getLogger('crawlutils')


def crawl_packages(
        dbpath=None,
        root_dir='/',
        installed_since=0,
        reload_needed=True):

    # package attributes: ["installed", "name", "size", "version"]

    logger.debug('Crawling Packages')

    pkg_manager = _get_package_manager(root_dir)

    try:
        if pkg_manager == 'dpkg':
            dbpath = dbpath or 'var/lib/dpkg'
            for (key, feature) in get_dpkg_packages(
                    root_dir, dbpath, installed_since):
                yield (key, feature, 'package')
        elif pkg_manager == 'rpm':
            dbpath = dbpath or 'var/lib/rpm'
            for (key, feature) in get_rpm_packages(
                    root_dir, dbpath, installed_since, reload_needed):
                yield (key, feature, 'package')
        else:
            logger.warning('Unsupported package manager for Linux distro')
    except Exception as e:
        logger.error('Error crawling packages',
                     exc_info=True)
        raise CrawlError(e)


def _get_package_manager(root_dir):
    result = osinfo.get_osinfo(mount_point=root_dir)
    if result:
        os_distro = result['os']
    else:
        raise CrawlUnsupportedPackageManager()

    pkg_manager = None
    if os_distro in ['ubuntu', 'debian']:
        pkg_manager = 'dpkg'
    elif os_distro in ['redhat', 'red hat', 'rhel', 'fedora', 'centos']:
        pkg_manager = 'rpm'
    elif os.path.exists(os.path.join(root_dir, 'var/lib/dpkg')):
        pkg_manager = 'dpkg'
    elif os.path.exists(os.path.join(root_dir, 'var/lib/rpm')):
        pkg_manager = 'rpm'
    return pkg_manager
