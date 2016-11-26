import time
import uuid


class BaseFrame:

    def __init__(self, feature_types):
        self.data = []
        self.metadata = {}
        self.metadata['features'] = ','.join(map(str, feature_types))
        self.metadata['timestamp'] = int(time.time())
        self.metadata['uuid'] = str(uuid.uuid4())
        self.num_features = 0

    def add_features(self, features=[]):
        """features is a list of (str, FeatureObject, str)"""
        self.data.extend(features)
        self.num_features += len(features)

    def __str__(self):
        return '\n'.join(str(feature) for feature in self.data)


class BaseCrawler:

    def __init__(self, features=['os', 'cpu'],
                 plugin_places=['plugins'],
                 options={}):
        self.features = features
        self.plugin_places = plugin_places
        self.options = options

    def crawl(self, ignore_plugin_exception=True):
        """
        Crawl to get a snapshot frame of all systems.

        :param ignore_plugin_exception: ignore exceptions raised on a plugin
        :return: a list generator of Frame objects
        """
        pass
