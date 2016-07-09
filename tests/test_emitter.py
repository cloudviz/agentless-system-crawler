from capturing import Capturing
import unittest
# import docker
# import requests.exceptions
# import tempfile
# import os
# import shutil
# import subprocess

from crawler.emitter import Emitter


class NamespaceLibTests(unittest.TestCase):
    image_name = 'alpine:latest'

    def setUp(self):
        pass

    def tearDown(self):
        pass

    # Tests the Emitter crawler class
    # Throws an AssertionError if any test fails
    def _test_emitter_csv_simple_stdout(self):
        with Emitter(urls=['stdout://']) as emitter:
            emitter.emit("dummy_feature", {'test': 'bla', 'test2': 12345, 'test3': 12345.0, 'test4': 12345.00000},
                         'dummy_feature')

    def test_emitter_csv_simple_stdout(self):
        with Capturing() as _output:
            self._test_emitter_csv_simple_stdout()
        output = "%s" % _output
        assert len(_output) == 2
        assert "dummy_feature" in output
        assert "metadata" in output

    def test_emitter_csv_simple_file(self):
        with Emitter(urls=['file:///tmp/test_emitter_csv_simple_file']) as emitter:
            emitter.emit("dummy_feature", {'test': 'bla', 'test2': 12345, 'test3': 12345.0, 'test4': 12345.00000},
                         'dummy_feature')
        with open('/tmp/test_emitter_csv_simple_file') as f:
            _output = f.readlines()
            output = "%s" % _output
            assert len(_output) == 2
            assert "dummy_feature" in output
            assert "metadata" in output

    # Tests the Emitter crawler class
    # Throws an AssertionError if any test fails
    def _test_emitter_graphite_simple_stdout(self):
        metadata = {}
        metadata['namespace'] = 'namespace777'
        with Emitter(urls=['stdout://'], emitter_args=metadata, format='graphite') as emitter:
            emitter.emit("dummy_feature", {'test': 'bla', 'test2': 12345, 'test3': 12345.0, 'test4': 12345.00000},
                         'dummy_feature')

    def test_emitter_graphite_simple_stdout(self):
        with Capturing() as _output:
            self._test_emitter_graphite_simple_stdout()
        output = "%s" % _output
        # should look like this:
        # ['namespace777.dummy-feature.test3 3.000000 1449870719',
        #  'namespace777.dummy-feature.test2 2.000000 1449870719',
        #  'namespace777.dummy-feature.test4 4.000000 1449870719']
        assert len(_output) == 3
        assert "dummy_feature" not in output  # can't have '_'
        assert "dummy-feature" in output  # can't have '_'
        assert "metadata" not in output
        assert 'namespace777.dummy-feature.test2' in output
        assert 'namespace777.dummy-feature.test3' in output
        assert 'namespace777.dummy-feature.test4' in output
        assert len(_output[0].split(' ')) == 3  # three fields in graphite format
        assert len(_output[1].split(' ')) == 3  # three fields in graphite format
        assert len(_output[2].split(' ')) == 3  # three fields in graphite format
        assert float(_output[0].split(' ')[1]) == 12345.0
        assert float(_output[1].split(' ')[1]) == 12345.0
        assert float(_output[2].split(' ')[1]) == 12345.0

    def test_emitter_graphite_simple_file(self):
        metadata = {}
        metadata['namespace'] = 'namespace777'
        with Emitter(urls=['file:///tmp/test_emitter_graphite_simple_file'],
                     emitter_args=metadata, format='graphite') as emitter:
            emitter.emit("dummy_feature", {'test': 'bla', 'test2': 12345, 'test3': 12345.0, 'test4': 12345.00000},
                         'dummy_feature')
        with open('/tmp/test_emitter_graphite_simple_file') as f:
            _output = f.readlines()
            output = "%s" % _output
            # should look like this:
            # ['namespace777.dummy-feature.test3 3.000000 1449870719',
            #  'namespace777.dummy-feature.test2 2.000000 1449870719',
            #  'namespace777.dummy-feature.test4 4.000000 1449870719']
            assert len(_output) == 3
            assert "dummy_feature" not in output  # can't have '_'
            assert "dummy-feature" in output  # can't have '_'
            assert "metadata" not in output
            assert 'namespace777.dummy-feature.test2' in output
            assert 'namespace777.dummy-feature.test3' in output
            assert 'namespace777.dummy-feature.test4' in output
            assert len(_output[0].split(' ')) == 3  # three fields in graphite format
            assert len(_output[1].split(' ')) == 3  # three fields in graphite format
            assert len(_output[2].split(' ')) == 3  # three fields in graphite format
            assert float(_output[0].split(' ')[1]) == 12345.0
            assert float(_output[1].split(' ')[1]) == 12345.0
            assert float(_output[2].split(' ')[1]) == 12345.0
