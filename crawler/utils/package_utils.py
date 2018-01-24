import logging
import os
import shutil
import tempfile

from crawler_exceptions import CrawlError, CrawlUnsupportedPackageManager
from utils import osinfo
from utils.features import PackageFeature
from utils.misc import subprocess_run

logger = logging.getLogger('crawlutils')


def get_dpkg_packages(
        root_dir='/',
        dbpath='var/lib/dpkg',
        installed_since=0):

    if os.path.isabs(dbpath):
        logger.warning(
            'dbpath: ' +
            dbpath +
            ' is defined absolute. Ignoring prefix: ' +
            root_dir +
            '.')

    # Update for a different route.

    dbpath = os.path.join(root_dir, dbpath)

    output = subprocess_run(['dpkg-query', '-W',
                             '--admindir={0}'.format(dbpath),
                             '-f=${Package}|${Version}'
                             '|${Architecture}|${Installed-Size}\n'],
                            shell=False)
    dpkglist = output.strip('\n')
    if dpkglist:
        for dpkginfo in dpkglist.split('\n'):
            (name, version, architecture, size) = dpkginfo.split(r'|')

            # dpkg does not provide any installtime field
            # feature_key = '{0}/{1}'.format(name, version) -->
            # changed to below per Suriya's request

            feature_key = '{0}'.format(name, version)
            yield (feature_key, PackageFeature(None, name,
                                               size, version,
                                               architecture))


def get_rpm_packages(
        root_dir='/',
        dbpath='var/lib/rpm',
        installed_since=0,
        reload_needed=False):

    if os.path.isabs(dbpath):
        logger.warning(
            'dbpath: ' +
            dbpath +
            ' is defined absolute. Ignoring prefix: ' +
            root_dir +
            '.')

    # update for a different route

    dbpath = os.path.join(root_dir, dbpath)

    try:
        if reload_needed:
            reloaded_db_dir = tempfile.mkdtemp()
            _rpm_reload_db(root_dir, dbpath, reloaded_db_dir)
            dbpath = reloaded_db_dir

        output = subprocess_run(['rpm',
                                 '--dbpath',
                                 dbpath,
                                 '-qa',
                                 '--queryformat',
                                 '%{installtime}|%{name}|%{version}'
                                 '-%{release}|%{arch}|%{size}\n'],
                                shell=False,
                                ignore_failure=True)
        # We ignore failures because sometimes rpm returns rc=1 but still
        # outputs all the data.
        rpmlist = output.strip('\n')
    finally:
        if reload_needed:
            logger.debug('Deleting directory: %s' % (reloaded_db_dir))
            shutil.rmtree(reloaded_db_dir)

    if rpmlist:
        for rpminfo in rpmlist.split('\n'):
            (installtime, name, version, architecture, size) = \
                rpminfo.split(r'|')
            """
            if int(installtime) <= installed_since: --> this
            barfs for sth like: 1376416422. Consider try: xxx
            except ValueError: pass
            """

            if installtime <= installed_since:
                continue
            """
            feature_key = '{0}/{1}'.format(name, version) -->
            changed to below per Suriya's request
            """

            feature_key = '{0}'.format(name, version)
            yield (feature_key,
                   PackageFeature(installtime,
                                  name, size, version, architecture))


def _rpm_reload_db(
        root_dir='/',
        dbpath='var/lib/rpm',
        reloaded_db_dir='/tmp/'):
    """
    Dumps and reloads the rpm database.

    Returns the path to the new rpm database, or raises RuntimeError if the
    dump and load commands failed.
    """

    try:
        dump_dir = tempfile.mkdtemp()

        subprocess_run(['/usr/bin/db_dump',
                        os.path.join(dbpath, 'Packages'),
                        '-f',
                        os.path.join(dump_dir, 'Packages')],
                       shell=False)
        subprocess_run(['/usr/bin/db_load',
                        '-f',
                        os.path.join(dump_dir, 'Packages'),
                        os.path.join(reloaded_db_dir, 'Packages')],
                       shell=False)
    finally:
        logger.debug('Deleting directory: %s' % (dump_dir))
        shutil.rmtree(dump_dir)

    return reloaded_db_dir

# from UK crawler codebase


def apk_parser(filename):
    try:
        db_contents = open(filename).read()
        packages = db_contents.split('\n\n')
        logger.debug('Found {} APK packages'.format(len(packages)))
        for package in packages:
            if package:
                attributes = package.split('\n')
                name = ""
                version = ""
                architecture = ""
                size = ""
                for attribute in attributes:
                    if (attribute.startswith('P:')):
                        name = attribute[2:]
                    elif (attribute.startswith('V:')):
                        version = attribute[2:]
                    elif (attribute.startswith('A:')):
                        architecture = attribute[2:]
                    elif (attribute.startswith('S:')):
                        size = attribute[2:]
                yield (name, PackageFeature(None, name,
                                            size, version,
                                            architecture))
    except IOError as e:
        logger.error('Failed to read APK database to obtain packages. '
                     'Check if %s is present.  [Exception: %s: %s]'
                     ' ' % (filename, type(e).__name__, e.strerror))
        raise


def get_apk_packages(
        root_dir='/',
        dbpath='lib/apk/db'):

    if os.path.isabs(dbpath):
        logger.warning(
            'dbpath: ' +
            dbpath +
            ' is defined absolute. Ignoring prefix: ' +
            root_dir +
            '.')

    # Update for a different route.
    dbpath = os.path.join(root_dir, dbpath)

    for feature_key, package_feature in apk_parser(
            os.path.join(dbpath, 'installed')):
        yield (feature_key, package_feature)


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
        elif pkg_manager == 'apk':
            dbpath = dbpath or 'lib/apk/db'
            for (key, feature) in get_apk_packages(
                    root_dir, dbpath):
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
    if os_distro in ['alpine']:
        pkg_manager = 'apk'
    elif os.path.exists(os.path.join(root_dir, 'var/lib/dpkg')):
        pkg_manager = 'dpkg'
    elif os.path.exists(os.path.join(root_dir, 'var/lib/rpm')):
        pkg_manager = 'rpm'
    return pkg_manager
