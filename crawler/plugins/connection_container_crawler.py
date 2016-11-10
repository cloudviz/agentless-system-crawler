try:
    import crawler.dockerutils as dockerutils
    from crawler.icrawl_plugin import IContainerCrawler
    from crawler.namespace import run_as_another_namespace, ALL_NAMESPACES
    from crawler.plugins.connection_crawler import crawl_connections
except ImportError:
    import dockerutils
    from icrawl_plugin import IContainerCrawler
    from namespace import run_as_another_namespace, ALL_NAMESPACES
    from plugins.connection_crawler import crawl_connections

import logging

logger = logging.getLogger('crawlutils')


class ConnectionContainerCrawler(IContainerCrawler):

    def get_feature(self):
        return 'connection'

    def crawl(self, container_id, avoid_setns=False, **kwargs):
        inspect = dockerutils.exec_dockerinspect(container_id)
        state = inspect['State']
        pid = str(state['Pid'])
        logger.debug(
            'Crawling %s for container %s' %
            (self.get_feature(), container_id))

        if avoid_setns:
            raise NotImplementedError('avoidsetns mode not implemented')
        else:  # in all other cases, including wrong mode set
            return run_as_another_namespace(pid,
                                            ALL_NAMESPACES,
                                            crawl_connections)
