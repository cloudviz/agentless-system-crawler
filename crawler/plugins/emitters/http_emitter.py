import logging
import time

import requests

from iemit_plugin import IEmitter

logger = logging.getLogger('crawlutils')


class HttpEmitter(IEmitter):

    def get_emitter_protocol(self):
        return 'http'

    def init(self, url, timeout=1, max_retries=5, emit_format='csv'):
        IEmitter.init(self, url,
                      timeout=timeout,
                      max_retries=max_retries,
                      emit_format=emit_format)
        if emit_format == 'json':
            self.emit_per_line = True

    def emit(self, frame, compress=False,
             metadata={}, snapshot_num=0):
        """

        :param frame: a frame containing extracted features
        :param compress:
        :param metadata:
        :param snapshot_num:
        :return: None
        """
        iostream = self.format(frame)
        if compress:
            raise NotImplementedError('http emitter does not support gzip.')
        if self.emit_per_line:
            iostream.seek(0)
            for line in iostream.readlines():
                self.post(line, metadata)
        else:
            self.post(iostream.getvalue(), metadata)

    def post(self, content='', metadata={}):
        headers = {'content-type': 'application/csv'}
        for attempt in range(self.max_retries):
            try:
                response = requests.post(self.url, headers=headers,
                                         params=metadata,
                                         data=content)
            except requests.exceptions.ChunkedEncodingError as e:
                logger.exception(e)
                logger.error(
                    "POST to %s resulted in exception (attempt %d of %d), "
                    "Exiting." % (self.url, attempt + 1, self.max_retries))
                break
            except requests.exceptions.RequestException as e:
                logger.exception(e)
                logger.error(
                    "POST to %s resulted in exception (attempt %d of %d)" %
                    (self.url, attempt + 1, self.max_retries))
                time.sleep(2.0 ** attempt * 0.1)
                continue
            if response.status_code != requests.codes.ok:
                logger.error("POST to %s resulted in status code %s: %s "
                             "(attempt %d of %d)" %
                             (self.url, str(response.status_code),
                              response.text, attempt + 1, self.max_retries))
                time.sleep(2.0 ** attempt * 0.1)
            else:
                break
