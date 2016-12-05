import time
import uuid


class BaseFrame:

    def __init__(self, feature_types):
        """

        :param feature_types: list of feature types, e.g. ['os','cpu'].
        This list is just used to describe the features in a frame. No
        checks are made to verify that all features in this list
        have an actual feature in .data
        """
        self.data = []
        self.metadata = {}
        self.metadata['features'] = ','.join(map(str, feature_types))
        self.metadata['timestamp'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
        self.metadata['uuid'] = str(uuid.uuid4())
        self.num_features = 0

    def add_features(self, features=[]):
        """features is a list of (str, FeatureObject, str)"""
        self.data.extend(features)
        self.num_features += len(features)

    def add_feature(self, feature_type, feature_key, feature_value):
        self.data.append((feature_type, feature_key, feature_value))
        self.num_features += 1

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
