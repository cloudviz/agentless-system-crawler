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


class Crawler:

    def __init__(self,
                 emitters=None,
                 frequency=-1,
                 features=['os', 'cpu'],
                 plugin_places=['plugins'],
                 options={}):
        """
        Store and check the types of the arguments.

        :param emitters: EmittersManager that holds the list of Emitters.
        If it is None, then no emit is done.
        :param frequency: Sleep seconds between iterations
        """
        self.iter_count = 0
        self.frequency = frequency
        self.next_iteration_time = None
        self.emitters = emitters
        self.features = features
        self.plugin_places = plugin_places
        self.options = options

    def crawl(self, ignore_plugin_exception=True):
        """
        Crawl to get a list of snapshot frames for all systems.

        :param ignore_plugin_exception: ignore exceptions raised on a plugin
        :return: a list generator of Frame objects
        """
        raise NotImplementedError('crawl method implementation is missing.')

    def polling_crawl(self, timeout, ignore_plugin_exception=True):
        """
        Crawl to get a snapshot frame of any new system created before
        `timeout` seconds.

        :param timeout: seconds to wait for new systems
        :param ignore_plugin_exception: ignore exceptions raised on a plugin
        :return: a Frame object or None if no system was created.
        """
        if timeout > 0:
            time.sleep(timeout)
        return None

    def iterate(self, timeout):
        """
        Function called at each iteration.

        Side effects: increments iter_count

        :param timeout: seconds to wait for polling crawls.
        :return: None
        """

        # Start by polling new systems created within `timeout` seconds
        end_time = time.time() + timeout
        while timeout > 0:
            # If polling is not implemented, this is a sleep(timeout)
            frame = self.polling_crawl(timeout)
            if frame and self.emitters:
                self.emitters.emit(frame, snapshot_num=self.iter_count)
            timeout = end_time - time.time()
            # just used for output purposes
            self.iter_count += 1

        # Crawl all systems now
        for frame in self.crawl():
            if self.emitters is not None:
                self.emitters.emit(frame, snapshot_num=self.iter_count)

        # just used for output purposes
        self.iter_count += 1

    def _get_next_iteration_time(self, snapshot_time):
        """
        Returns the number of seconds to sleep before the next iteration.

        :param snapshot_time: Start timestamp of the current iteration.
        :return: Seconds to sleep as a float.
        """
        if self.frequency == 0:
            return 0

        if self.next_iteration_time is None:
            self.next_iteration_time = snapshot_time + self.frequency
        else:
            self.next_iteration_time += self.frequency

        while self.next_iteration_time + self.frequency < time.time():
            self.next_iteration_time += self.frequency

        time_to_sleep = self.next_iteration_time - time.time()
        return time_to_sleep

    def run(self):
        """
        Main crawler loop. Each iteration is one crawl and a sleep.

        :return: None
        """
        time_to_sleep = 0
        while True:
            snapshot_time = time.time()
            self.iterate(time_to_sleep)
            # Frequency < 0 means only one run.
            if self.frequency < 0:
                break
            time_to_sleep = self._get_next_iteration_time(snapshot_time)
