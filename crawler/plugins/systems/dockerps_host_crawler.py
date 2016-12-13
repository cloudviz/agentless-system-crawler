import logging

from icrawl_plugin import IHostCrawler
from utils.dockerutils import exec_dockerps
from utils.features import DockerPSFeature

logger = logging.getLogger('crawlutils')


class DockerpsHostCrawler(IHostCrawler):

    def get_feature(self):
        return 'dockerps'

    def crawl(self, **kwargs):
        logger.debug('Crawling %s' % (self.get_feature()))

        for inspect in exec_dockerps():
            yield (inspect['Id'], DockerPSFeature._make([
                inspect['State']['Running'],
                0,
                inspect['Image'],
                [],
                inspect['Config']['Cmd'],
                inspect['Name'],
                inspect['Id'],
            ]), 'dockerps')
