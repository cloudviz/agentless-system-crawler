import mock
import unittest
import os

import crawler.package_utils
from crawler.features import PackageFeature

def mocked_subprocess_run(cmd, shell=False, ignore_failure=False):
    if 'dpkg-query' in cmd:
        return ('pkg1|v1|x86|123\n'
                'pkg2|v2|x86|123')
    elif '--queryformat' in cmd:
        return ('123|pkg1|v1|x86|123\n'
                '123|pkg1|v1|x86|123\n')

class PackageUtilsTests(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    @mock.patch('crawler.package_utils.subprocess_run',
                side_effect=mocked_subprocess_run)
    def test_get_dpkg_packages(self, mock_subprocess_run):
        pkgs = list(crawler.package_utils.get_dpkg_packages())
        print pkgs
        assert pkgs == [('pkg1', PackageFeature(installed=None, pkgname='pkg1', pkgsize='123', pkgversion='v1', pkgarchitecture='x86')), ('pkg2', PackageFeature(installed=None, pkgname='pkg2', pkgsize='123', pkgversion='v2', pkgarchitecture='x86'))]

    @mock.patch('crawler.package_utils.subprocess_run',
                side_effect=mocked_subprocess_run)
    def test_get_rpm_packages(self, mock_subprocess_run):
        pkgs = list(crawler.package_utils.get_rpm_packages())
        print pkgs
        assert pkgs == [('pkg1', PackageFeature(installed='123', pkgname='pkg1', pkgsize='123', pkgversion='v1', pkgarchitecture='x86')), ('pkg1', PackageFeature(installed='123', pkgname='pkg1', pkgsize='123', pkgversion='v1', pkgarchitecture='x86'))]

    @mock.patch('crawler.package_utils.subprocess_run',
                side_effect=mocked_subprocess_run)
    def test_get_rpm_packages_with_db_reload(self, mock_subprocess_run):
        pkgs = list(crawler.package_utils.get_rpm_packages(reload_needed=True))
        print pkgs
        assert pkgs == [('pkg1', PackageFeature(installed='123', pkgname='pkg1', pkgsize='123', pkgversion='v1', pkgarchitecture='x86')), ('pkg1', PackageFeature(installed='123', pkgname='pkg1', pkgsize='123', pkgversion='v1', pkgarchitecture='x86'))]

