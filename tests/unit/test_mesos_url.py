# test.py
from mock import patch, Mock
from crawler.mesos import fetch_stats

@patch('crawler.mesos.urllib2.urlopen')
def mytest(mock_urlopen):
    a = Mock()
    a.read.side_effect = ['{}', None]
    mock_urlopen.return_value = a
    res = fetch_stats("0.22.0")
    print res
    if res == None:
        assert res


mytest()
