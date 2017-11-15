from __future__ import absolute_import
from . import plugins_manager
from .base_crawler import BaseCrawler, BaseFrame


class HostFrame(BaseFrame):

    def __init__(self, feature_types, namespace):
        BaseFrame.__init__(self, feature_types)
        self.metadata['namespace'] = namespace
        self.metadata['system_type'] = 'host'


class HostCrawler(BaseCrawler):

    def __init__(self,
                 features=['os', 'cpu'], namespace='',
                 plugin_places=['plugins'], options={}):
        BaseCrawler.__init__(
            self,
            features=features,
            plugin_places=plugin_places)
        plugins_manager.reload_host_crawl_plugins(
            features, plugin_places, options)
        self.plugins = plugins_manager.get_host_crawl_plugins(
            features=features)
        self.namespace = namespace

    def crawl(self, ignore_plugin_exception=True):
        """
        Crawl the host with all the plugins loaded on __init__

        :param ignore_plugin_exception: just ignore exceptions on a plugin
        :return: a list generator with a frame object
        """
        frame = HostFrame(self.features, self.namespace)
        for (plugin_obj, plugin_args) in self.plugins:
            try:
                frame.add_features(plugin_obj.crawl(**plugin_args))
            except Exception as exc:
                if not ignore_plugin_exception:
                    raise exc
        yield frame
