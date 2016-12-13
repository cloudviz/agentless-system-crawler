import time


class Worker:

    def __init__(self,
                 emitters=None,
                 frequency=-1,
                 crawler=None):
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
            self.crawler = crawler

    def iterate(self, timeout=0):
        """
        Function called at each iteration.

        Side effects: increments iter_count

        :param timeout: seconds to wait for polling crawls. If 0, then
        just use the regular crawl() method and do not poll.
        :return: None
        """

        # Start by polling new systems created within `timeout` seconds
        end_time = time.time() + timeout
        while timeout > 0:
            # If polling is not implemented, this is a sleep(timeout)
            frame = self.crawler.polling_crawl(timeout)
            if frame and self.emitters:
                self.emitters.emit(frame, snapshot_num=self.iter_count)
            timeout = end_time - time.time()
            # just used for output purposes
            self.iter_count += 1

        # Crawl all systems now
        for frame in self.crawler.crawl():
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
