import mock
import unittest

from crawler.container import Container


def mocked_exists(pid):
    return True


class ContainerTests(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_non_implemented_methods(self):
        c = Container(1)
        with self.assertRaises(NotImplementedError):
            c.get_memory_cgroup_path()
        with self.assertRaises(NotImplementedError):
            c.get_cpu_cgroup_path()

    @mock.patch('crawler.container.os.path.exists', side_effect=mocked_exists)
    def test_is_running(self, mock_exists):
        c = Container(1)
        assert c.is_running()

    def test_eq_ne(self):
        c1 = Container(1)
        c2 = Container(2)
        c3 = Container(2)
        assert c1 != c2
        assert c2 == c3

    def test_is_docker(self):
        c = Container(1)
        assert not c.is_docker_container()

    def test_to_str(self):
        c = Container(1)
        print(c)
