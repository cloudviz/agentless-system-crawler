import logging
import time

import requests

try:
    from plugins.emitters.base_emitter import BaseEmitter
except ImportError:
    from crawler.plugins.emitters.base_emitter import BaseEmitter

logger = logging.getLogger('crawlutils')


class HttpEmitter(BaseEmitter):
    def __init__(self, url, timeout=1, max_retries=5,
                 emit_per_line=False):
        BaseEmitter.__init__(self, url,
                             timeout=timeout,
                             max_retries=max_retries,
                             emit_per_line=emit_per_line)

    def emit(self, iostream, compress=False,
             metadata={}, snapshot_num=0):
        """

        :param iostream: a CStringIO used to buffer the formatted features.
        :param compress:
        :param metadata:
        :param snapshot_num:
        :return: None
        """
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
