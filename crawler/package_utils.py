import os
import subprocess
import logging
import tempfile
import shutil

from misc import subprocess_run
from features import PackageFeature

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
                                 shell=False)
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

        _ = subprocess_run(['/usr/bin/db_dump',
                            os.path.join(dbpath, 'Packages'),
                            '-f',
                            os.path.join(dump_dir, 'Packages')],
                            shell=False)
        _ = subprocess_run(['/usr/bin/db_load',
                            '-f',
                            os.path.join(dump_dir, 'Packages'),
                            os.path.join(reloaded_db_dir, 'Packages')],
                            shell=False)
    finally:
        logger.debug('Deleting directory: %s' % (dump_dir))
        shutil.rmtree(dump_dir)

    return reloaded_db_dir
