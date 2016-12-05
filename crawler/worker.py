import time
from base_crawler import BaseCrawler


class Worker:
    """
    Main scheduler class. This class is just one never ending loop in run()
    that gets a list of frames from crawler.crawl() and sends them to
    the emitters using emitters.emit().
    """

    def __init__(self, emitters, frequency, crawler):
        """
        Store and check the types of the arguments.

        :param emitters: EmittersManager that holds the list of Emitters.
        If it is None, then no emit is done.
        :param frequency: Sleep seconds between iterations
        :param crawler: Crawler object with a crawl() method. This object
        maintains a list of crawler plugins, each with their own crawl()
        method.
        """
        if not isinstance(crawler, BaseCrawler):
            raise TypeError('crawler is not of type BaseCrawler')
        self.iter_count = 0
        self.frequency = frequency
        self.next_iteration_time = None
        self.crawler = crawler
        self.emitters = emitters

    def iterate(self):
        """
        Function called at each iteration.
        Side effects: increments iter_count

        :return: None
        """
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
