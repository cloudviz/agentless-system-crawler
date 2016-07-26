# test.py
from mock import patch, Mock
from config_and_metrics_crawler.crawler_mesos import fetch_stats
from config_and_metrics_crawler.crawler_mesos import CONFIGS

@patch('config_and_metrics_crawler.crawler_mesos.urllib2.urlopen')
def mytest(mock_urlopen):
    a = Mock()
    a.read.side_effect = ['{}', None]
    mock_urlopen.return_value = a
    res = fetch_stats("0.22.0")
    print res
    if res == None:
       assert res


mytest()
