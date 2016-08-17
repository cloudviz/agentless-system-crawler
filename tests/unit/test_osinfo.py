from unittest import TestCase
import unittest
import mock
from crawler.osinfo import (_get_file_name,
                    parse_lsb_release, 
                    parse_os_release, 
                    parse_redhat_release, 
                    parse_centos_release,
                    get_osinfo_from_lsb_release,
                    get_osinfo_from_os_release,
                    get_osinfo_from_redhat_centos
                    )

class Test_osinfo(TestCase):

    def test_get_file_name(self):
        self.assertEqual(_get_file_name('/', 'xyz'), '/xyz')
        self.assertEqual(_get_file_name('/abc/def', 'xyz'), '/abc/def/xyz')

    def test_parse_lsb_release(self):
        data = ['DISTRIB_ID=Ubuntu', 'DISTRIB_RELEASE=15.10', 
                'DISTRIB_CODENAME=wily' 'DISTRIB_DESCRIPTION="Ubuntu 15.10"']
        result = parse_lsb_release(data)

        self.assertEqual(result['os'], 'ubuntu')
        self.assertEqual(result['version'], '15.10')

    def test_parse_os_release(self):
        data = [ 'NAME="Ubuntu"', 'VERSION="14.04.4 LTS, Trusty Tahr"',
                 'ID=ubuntu', 'ID_LIKE=debian', 
                 'PRETTY_NAME="Ubuntu 14.04.4 LTS"', 'VERSION_ID="14.04"', 
                 'HOME_URL="http://www.ubuntu.com/"',
                 'SUPPORT_URL="http://help.ubuntu.com/"',
                 'BUG_REPORT_URL="http://bugs.launchpad.net/ubuntu/"'
                ]
        result = parse_os_release(data)
        self.assertEqual(result['os'], 'ubuntu')
        self.assertEqual(result['version'], '14.04')

    def test_alpine_parse_os_release(self):
        data = [ 'NAME="Alpine Linux"',
                'ID=alpine',
                'VERSION_ID=3.4.0',
                'PRETTY_NAME="Alpine Linux v3.4"',
                'HOME_URL="http://alpinelinux.org"',
                'BUG_REPORT_URL="http://bugs.alpinelinux.org"'
               ]

        result = parse_os_release(data)
        self.assertEqual(result['os'], 'alpine')
        self.assertEqual(result['version'], '3.4.0')

    def test_parse_redhat_release(self):
        data = ['Red Hat Enterprise Linux Server release 7.2 (Maipo)']

        result = parse_redhat_release(data)
        self.assertEqual(result['os'], 'rhel')
        self.assertEqual(result['version'], '7.2')

    def test2_parse_redhat_release(self):
        data = ['Red Hat Enterprise Linux Server release 7 (Maipo)']

        result = parse_redhat_release(data)
        self.assertEqual(result['os'], 'rhel')
        self.assertEqual(result['version'], '7')

    def test_parse_centos_release(self):
        data = ['CentOS release 6.8 (Final)']

        result = parse_centos_release(data)
        self.assertEqual(result['os'], 'centos')
        self.assertEqual(result['version'], '6.8')

    def test2_parse_centos_release(self):
        data = ['CentOS Linux release 6.8 (Final)']

        result = parse_centos_release(data)
        self.assertEqual(result['os'], 'centos')
        self.assertEqual(result['version'], '6.8')

    def test3_parse_centos_release(self):
        data = ['CentOS release 6 (Final)']

        result = parse_centos_release(data)
        self.assertEqual(result['os'], 'centos')
        self.assertEqual(result['version'], '6')

    def test_get_osinfo_from_lsb_release(self):
        data = ['DISTRIB_ID=Ubuntu', 'DISTRIB_RELEASE=15.10', 
                'DISTRIB_CODENAME=wily' 'DISTRIB_DESCRIPTION="Ubuntu 15.10"']
        with mock.patch('__builtin__.open', mock.mock_open(read_data="\n".join(data)), \
                        create=True) as m:
            m.return_value.__iter__.return_value = data

            result = get_osinfo_from_lsb_release()
            self.assertEqual(result['os'], 'ubuntu')
            self.assertEqual(result['version'], '15.10')

    def test1_get_osinfo_from_lsb_release(self):
        with mock.patch('__builtin__.open', mock.mock_open(), create=True) as m:
            m.side_effect = IOError()

            result = get_osinfo_from_lsb_release()
            self.assertFalse(result)

    def test_get_osinfo_from_os_release(self):
        data = [ 'NAME="Ubuntu"', 'VERSION="14.04.4 LTS, Trusty Tahr"',
                 'ID=ubuntu', 'ID_LIKE=debian', 
                 'PRETTY_NAME="Ubuntu 14.04.4 LTS"', 'VERSION_ID="14.04"', 
                 'HOME_URL="http://www.ubuntu.com/"',
                 'SUPPORT_URL="http://help.ubuntu.com/"',
                 'BUG_REPORT_URL="http://bugs.launchpad.net/ubuntu/"'
                ]
        with mock.patch('__builtin__.open', mock.mock_open(read_data="\n".join(data)), \
                        create=True) as m:
            m.return_value.__iter__.return_value = data

            result = get_osinfo_from_os_release()
            self.assertEqual(result['os'], 'ubuntu')
            self.assertEqual(result['version'], '14.04')

    def test1_get_osinfo_from_os_release(self):
        with mock.patch('__builtin__.open', mock.mock_open(), create=True) as m:
            m.side_effect = IOError()

            result = get_osinfo_from_os_release()
            self.assertFalse(result)

    def test_get_osinfo_from_redhat_centos(self):
        data = ['Red Hat Enterprise Linux Server release 7.2 (Maipo)']
        with mock.patch('__builtin__.open', mock.mock_open(read_data="\n".join(data)), \
                        create=True) as m:
            m.return_value.__iter__.return_value = data

            result = get_osinfo_from_redhat_centos()
            self.assertEqual(result['os'], 'rhel')
            self.assertEqual(result['version'], '7.2')

    def mtest1_get_osinfo_from_redhat_centos(self):
        with mock.patch('__builtin__.open', mock.mock_open(), create=True) as m:
            m.side_effect = IOError()

            result = get_osinfo_from_redhat_centos()
            self.assertFalse(result)
if __name__ == '__main__':
    unittest.main()
