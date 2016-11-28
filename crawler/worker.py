import time

from emitter import Emitter


class Worker:

    def __init__(self, emitter_args, frequency, crawler):
        self.iter_count = 0
        self.frequency = frequency
        self.next_iteration_time = None
        self.emitter_args = emitter_args
        self.crawler = crawler

    def iterate(self):
        """
        Function called at each iteration.
        Side effects: increments iter_count
        :return: None
        """
        for frame in self.crawler.crawl():
            # TODO: Emitter(s) should be passed as an argument for this object
            with Emitter(
                    metadata=frame.metadata,
                    snapshot_num=self.iter_count,
                    **self.emitter_args
            ) as emitter:
                for (key, val, feature_type) in frame.data:
                    emitter.emit(key, val, feature_type)

        # just used for output purposes
        self.iter_count += 1

    def _get_next_iteration_time(self, snapshot_time):
        """
        Returns the number of seconds to sleep before the next iteration.

        :param snapshot_time: Start timestamp of the current iteration.
        :return: Seconds to sleep as a float.
        """
        if self.frequency == 0:
            return 0, 0

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
        while True:
            snapshot_time = int(time.time())
            self.iterate()
            # Frequency < 0 means only one run.
            if self.frequency < 0:
                break
            time_to_sleep = self._get_next_iteration_time(snapshot_time)
            if time_to_sleep > 0:
                time.sleep(time_to_sleep)
