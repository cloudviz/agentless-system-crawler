'''
Unit tests for the DiskioHostCrawler plugin
'''
import unittest
import mock

from plugins.systems.diskio_host_crawler import DiskioHostCrawler

counters_increment = 0
time_increment = 0

def mocked_time():
    '''
    Used to mock time.time(), which the crawler calls to calculate rates
    '''
    global time_increment

    base_time = 1504726245
    return base_time + time_increment

def mocked_diskio_counters():
    '''
    Used to mock DiskContainerCrawler._crawl_disk_io_counters()
    '''
    global counters_increment

    base_counters = [10, 10, 10, 10]
    counters = [ i + counters_increment for i in base_counters]
    yield ('loop', [0, 0 , 0, 0])
    yield ('sda1', counters)

class TestDiskioCrawlerPlugin(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._crawler = DiskioHostCrawler()

    def testGetFeature(self):
        crawler = DiskioHostCrawler()
        self.assertEqual('diskio', crawler.get_feature())

    def test_crawl_disk_io_counters(self):
        crawler = DiskioHostCrawler()
        diskio_data = crawler._crawl_disk_io_counters()
        for device_name, counters in diskio_data:
            self.assertIsInstance(device_name, basestring)
            self.assertEqual(4, len(counters))
            for counter in counters:
                self.assertIsInstance(counter, (int, long))

    @mock.patch('time.time', side_effect=mocked_time)
    @mock.patch.object(DiskioHostCrawler, '_crawl_disk_io_counters', side_effect=mocked_diskio_counters)
    def testCrawl(self, mocked_diskio_counters, mocked_time):
        global counters_increment
        global time_increment

        # First crawl
        diskio_feature = self._crawler.crawl()
        for device_name, feature_attributes, feature_key in diskio_feature:
            self.assertEqual('diskio', feature_key)
            self.assertEqual(4, len(feature_attributes), 'Incorrect number of attributes')
            self.assertIsInstance(device_name, basestring, 'Device name should be string')

            self.assertEqual(0, feature_attributes.readoprate, 'Unexpected read operations per second')
            self.assertEqual(0, feature_attributes.writeoprate, 'Unexpected write operations per second')
            self.assertEqual(0, feature_attributes.readbytesrate, 'Unexpected bytes read per second')
            self.assertEqual(0, feature_attributes.writebytesrate, 'Unexpected bytes written per second')

            if device_name == 'diskio-loop':
                pass
            elif device_name == 'diskio-sda1':
                pass
            else:
                raise Exception('Unexpected device name')

        # Make sure counters will be incremented by mock the function mocking I/O counters
        counters_increment = 100.0

        # Make sure the time will be incremented by the mocked time.time()
        time_increment = 60

        # Second crawl
        diskio_feature = self._crawler.crawl()
        for device_name, feature_attributes, feature_key in diskio_feature:
            self.assertEqual('diskio', feature_key)
            self.assertEqual(4, len(feature_attributes), 'Incorrect number of attributes')
            self.assertIsInstance(device_name, basestring, 'Device name should be string')
            if device_name == 'diskio-loop':
                self.assertEqual(0, feature_attributes.readoprate, 'Unexpected read operations per second')
                self.assertEqual(0, feature_attributes.writeoprate, 'Unexpected write operations per second')
                self.assertEqual(0, feature_attributes.readbytesrate, 'Unexpected bytes read per second')
                self.assertEqual(0, feature_attributes.writebytesrate, 'Unexpected bytes written per second')
            elif device_name == 'diskio-sda1':
                expected_rate = round(counters_increment/time_increment, 2)
                self.assertEqual(feature_attributes.readoprate, expected_rate, 'Unexpected read operations per second')
                self.assertEqual(feature_attributes.writeoprate, expected_rate, 'Unexpected write operations per second')
                self.assertEqual(feature_attributes.readbytesrate, expected_rate, 'Unexpected bytes read per second')
                self.assertEqual(feature_attributes.writebytesrate, expected_rate, 'Unexpected bytes written per second')
            else:
                raise Exception('Unexpected device name')

        # Make sure the counter-diff as compared to the previous crawl will be negative,
        # to emulate a case where the OS counters have wrapped
        # In this case, the crawler is expected to report the same measurement as before  
        counters_increment = -500.0

        # Make sure the time will be incremented by the mocked time.time()
        time_increment += 60

        # Third crawl
        diskio_feature = self._crawler.crawl()        
        for device_name, feature_attributes, feature_key in diskio_feature:
            self.assertEqual('diskio', feature_key)
            self.assertEqual(4, len(feature_attributes), 'Incorrect number of attributes')
            self.assertIsInstance(device_name, basestring, 'Device name should be string')
            if device_name == 'diskio-loop':
                self.assertEqual(0, feature_attributes.readoprate, 'Unexpected read operations per second')
                self.assertEqual(0, feature_attributes.writeoprate, 'Unexpected write operations per second')
                self.assertEqual(0, feature_attributes.readbytesrate, 'Unexpected bytes read per second')
                self.assertEqual(0, feature_attributes.writebytesrate, 'Unexpected bytes written per second')
            elif device_name == 'diskio-sda1':
                self.assertEqual(feature_attributes.readoprate, expected_rate, 'Unexpected read operations per second')
                self.assertEqual(feature_attributes.writeoprate, expected_rate, 'Unexpected write operations per second')
                self.assertEqual(feature_attributes.readbytesrate, expected_rate, 'Unexpected bytes read per second')
                self.assertEqual(feature_attributes.writebytesrate, expected_rate, 'Unexpected bytes written per second')
            else:
                raise Exception('Unexpected device name')

if __name__ == "__main__":
    unittest.main()
