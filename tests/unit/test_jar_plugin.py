import unittest

import os
import sys
import tempfile
from zipfile import ZipFile, ZipInfo

from utils import jar_utils
from utils.features import JarFeature

#
# https://security.openstack.org/guidelines/dg_using-temporary-files-securely.html
#

sys.path.append('tests/unit/')
from plugins.systems.jar_host_crawler import JarHostCrawler


class GPUPluginTests(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_jar_host_crawler_plugin(self, *args):
        tmpdir = tempfile.mkdtemp()
        jar_file_name = 'myfile.jar'

        # Ensure the file is read/write by the creator only
        saved_umask = os.umask(0077)

        path = os.path.join(tmpdir, jar_file_name)
        try:
            with ZipFile(path, "w") as myjar:
                myjar.writestr(ZipInfo('first.class',(1980,1,1,1,1,1)), "first secrets!")
                myjar.writestr(ZipInfo('second.class',(1980,1,1,1,1,1)), "second secrets!")
                myjar.writestr(ZipInfo('second.txt',(1980,1,1,1,1,1)), "second secrets!")

            fc = JarHostCrawler()
            jars = list(fc.crawl(root_dir=tmpdir))
            #jars = list(jar_utils.crawl_jar_files(root_dir=tmpdir))
            print jars
            jar_feature = jars[0][1]
            assert 'myfile.jar' == jar_feature.name
            assert '48ac85a26ffa7ff5cefdd5c73a9fb888' == jar_feature.jarhash
            assert ['ddc6eff37020aa858e26b1ba8a49ee0e',
                    'cbe2a13eb99c1c8ac5f30d0a04f8c492'] == jar_feature.hashes
            assert 'jar' == jars[0][2]

        except IOError as e:
            print 'IOError'
        finally:
            os.remove(path)
            os.umask(saved_umask)
