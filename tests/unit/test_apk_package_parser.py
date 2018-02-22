# from UK crawler codebase
import unittest
from utils import package_utils
from utils.features import PackageFeature
import os
import logging

class PackageUtilsTest(unittest.TestCase):
   

    def test_single_package_is_parsed(self):
        input_file = os.path.join(os.path.dirname(__file__), 'single_package_apk_db')
        parser = package_utils.apk_parser(input_file)
        package = parser.next()
        self.assert_package_is_correct(package, 'test-package', '999.9.9', '999', 'x86_64')
        self.assertRaises(StopIteration, parser.next)
        
    def test_multiple_packages_parsed(self):
        input_file = os.path.join(os.path.dirname(__file__), 'two_packages_apk_db')
        parser = package_utils.apk_parser(input_file)
        self.assert_package_is_correct(parser.next(), 'first-package', '111.1.1', '111', 'x86_64')
        self.assert_package_is_correct(parser.next(), 'second-package', '222.2.2', '222', 'x86_64')
        self.assertRaises(StopIteration, parser.next)
        
    def test_error_message_produced(self):
        logger = logging.getLogger('crawlutils')
        log_handler = CapturingLogHandler()
        logger.addHandler(log_handler)
        with self.assertRaises(IOError):
            input_file = os.path.join(os.path.dirname(__file__), 'does.not.exist')
            parser = package_utils.apk_parser(input_file)
            parser.next()
        self.assertIsNotNone(log_handler.msg)
        self.assertIn('Failed to read APK database to obtain packages', log_handler.msg)
        self.assertIn('does.not.exist', log_handler.msg)
        self.assertIn('IOError: No such file or directory', log_handler.msg)
        
    def assert_package_is_correct(self, package, name, version, size, architecture):
        self.assertEqual(name, package[0])
        packageFeature = package[1]
        self.assertEqual(name, packageFeature.pkgname)
        self.assertEqual(version, packageFeature.pkgversion)
        self.assertEqual(size, packageFeature.pkgsize)
        self.assertEqual(architecture, packageFeature.pkgarchitecture)
        self.assertIsNone(packageFeature.installed)

class CapturingLogHandler(logging.Handler):
    msg = None
    def emit(self, record):
        self.msg = record.msg

if __name__ == '__main__':
    unittest.main()
