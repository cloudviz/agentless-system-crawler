import os
import subprocess
import logging
import tempfile
import shutil

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

    try:
        dpkg = subprocess.Popen(['dpkg-query', '-W',
                                 '--admindir={0}'.format(dbpath),
                                 '-f=${Package}|${Version}'
                                 '|${Architecture}|${Installed-Size}\n'
                                 ], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        dpkglist = dpkg.stdout.read().strip('\n')
    except OSError as e:
        logger.error(
            'Failed to launch dpkg query for packages. Check if '
            'dpkg-query is installed: [Errno: %d] ' %
            e.errno + e.strerror + ' [Exception: ' +
            type(e).__name__ + ']')
        dpkglist = None
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

        rpm = subprocess.Popen([
            'rpm',
            '--dbpath',
            dbpath,
            '-qa',
            '--queryformat',
            '%{installtime}|%{name}|%{version}'
            '-%{release}|%{arch}|%{size}\n',
        ], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        rpmlist = rpm.stdout.read().strip('\n')
    except OSError as e:
        logger.error(
            'Failed to launch rpm query for packages. Check if '
            'rpm is installed: [Errno: %d] ' %
            e.errno + e.strerror + ' [Exception: ' +
            type(e).__name__ + ']')
        rpmlist = None
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
    """Dumps and reloads the rpm database.

    Returns the path to the new rpm database, or raises RuntimeError or
    OSError.
    """

    try:
        dump_dir = tempfile.mkdtemp()

        proc = subprocess.Popen([
            '/usr/bin/db_dump',
            os.path.join(dbpath, 'Packages'),
            '-f',
            os.path.join(dump_dir, 'Packages'),
        ], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        output = proc.stdout.read()
        error_output = proc.stderr.read()
        (out, err) = proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError('rpmdb_dump failed with ' + error_output)

        proc = subprocess.Popen([
            '/usr/bin/db_load',
            '-f',
            os.path.join(dump_dir, 'Packages'),
            os.path.join(reloaded_db_dir, 'Packages'),
        ], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        output = proc.stdout.read()
        error_output = proc.stderr.read()
        (out, err) = proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError('rpmdb_dump failed with ' + error_output)
    finally:
        logger.debug('Deleting directory: %s' % (dump_dir))
        shutil.rmtree(dump_dir)

    return reloaded_db_dir
