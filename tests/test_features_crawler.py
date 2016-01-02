from capturing import Capturing
import sys
import subprocess

sys.path.append('..')

from crawler.emitter import Emitter
from crawler.features_crawler import FeaturesCrawler
from setup_logger import setup_logger

from crawler.dockercontainer import DockerContainer
from crawler.dockerutils import exec_dockerinspect


# Tests the FeaturesCrawler class
# Throws an AssertionError if any test fails

def test_features_crawler_crawl_invm_cpu():
    crawler = FeaturesCrawler(crawl_mode='INVM')
    cores = len(list(crawler.crawl_cpu()))
    assert cores > 0
    print sys._getframe().f_code.co_name, 1

def test_features_crawler_crawl_invm_mem():
    crawler = FeaturesCrawler(crawl_mode='INVM')
    cores = len(list(crawler.crawl_memory()))
    assert cores > 0
    print sys._getframe().f_code.co_name, 1

def test_features_crawler_crawl_outcontainer_cpu():
    # Start a dummy container
    proc = subprocess.Popen(
            "docker run -d ubuntu sleep 60",
            shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    long_id = proc.stdout.read().strip()
    c = DockerContainer(long_id)
    
    crawler = FeaturesCrawler(crawl_mode='OUTCONTAINER', container=c)
    #for key, feature in crawler.crawl_cpu():
    #    print key, feature
    cores = len(list(crawler.crawl_cpu()))
    # Kill the dummy container
    proc = subprocess.Popen(
            "docker rm -f %s" % long_id,
            shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    long_id = proc.stdout.read().strip()
    assert cores > 0
    print sys._getframe().f_code.co_name, 1

def test_features_crawler_crawl_outcontainer_mem():
    # Start a dummy container
    proc = subprocess.Popen(
            "docker run -d ubuntu sleep 60",
            shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    long_id = proc.stdout.read().strip()
    c = DockerContainer(long_id)

    crawler = FeaturesCrawler(crawl_mode='OUTCONTAINER', container=c)
    output = "%s" % list(crawler.crawl_memory())
    #print output
    # Kill the dummy container
    proc = subprocess.Popen(
            "docker rm -f %s" % long_id,
            shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    long_id = proc.stdout.read().strip()
    assert 'memory_used' in output
    print sys._getframe().f_code.co_name, 1


if __name__ == '__main__':
    setup_logger("crawlutils", "tester.log")
    test_features_crawler_crawl_invm_cpu()
    test_features_crawler_crawl_outcontainer_cpu()
    test_features_crawler_crawl_invm_mem()
    test_features_crawler_crawl_outcontainer_mem()
