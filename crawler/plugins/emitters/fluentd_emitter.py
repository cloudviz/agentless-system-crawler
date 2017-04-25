import logging

from iemit_plugin import IEmitter
from utils.crawler_exceptions import EmitterUnsupportedFormat
from utils.misc import call_with_retries
from fluent import sender
import time

logger = logging.getLogger('crawlutils')


class FluentdEmitter(IEmitter):

    def get_emitter_protocol(self):
        return 'fluentd'

    def init(self, url, timeout=1, max_retries=5, emit_format='fluentd'):
        self.url = url
        self.timeout = timeout
        self.max_retries = max_retries
        self.emit_per_line = True

        if emit_format != 'json':
            raise EmitterUnsupportedFormat('Not supported: %s' % emit_format)

        try:
            # assumption URL fot fluentd engine is of form fuentd://IP:PORT
            host, port = url[len('fluentd://'):].split(':')
        except (KeyError, TypeError) as exc:
            logger.warn('Can not parse the url provided.')
            raise exc

        self.fluentd_sender = None

        call_with_retries(self.connect_to_fluentd_engine,
                          max_retries=self.max_retries,
                          _args=tuple((host, int(port))))

    def connect_to_fluentd_engine(self, host, port):
        self.fluentd_sender = sender.FluentSender(
            'crawler', host=host, port=port)
        if self.fluentd_sender.socket is None:
            raise Exception

    def get_json_item(self, frame):
        yield frame.metadata
        for (key, val, feature_type) in frame.data:
            output = dict()
            if not isinstance(val, dict):
                val = val._asdict()
            output['feature_type'] = feature_type
            output['feature_key'] = key
            output['feature_val'] = val
            yield output

    def emit_frame_atonce(self, tag, timestamp, frame):
        combined_dict = dict()
        item_count = 0

        for json_item in self.get_json_item(frame):
            key = 'feature' + str(item_count)
            combined_dict[key] = json_item
            item_count += 1

        self._emit(tag, timestamp, combined_dict)

    def _emit(self, tag, timestamp, item):
        self.fluentd_sender.emit_with_time(tag, timestamp, item)
        if self.fluentd_sender.last_error is not None:
            self.fluentd_sender.clear_last_error()
            raise Exception

    def emit(self, frame, compress=False,
             metadata={}, snapshot_num=0, **kwargs):
        """

        :param compress:
        :param metadata:
        :param snapshot_num:
        :return:
        """
        if compress:
            raise NotImplementedError('Compress not implemented.')

        tag = frame.metadata.get('namespace', '')
        timestamp = frame.metadata.get('timestamp', '')
        timestamp = time.mktime(
            time.strptime(timestamp[:-5], '%Y-%m-%dT%H:%M:%S'))

        if self.emit_per_line:
            for json_item in self.get_json_item(frame):
                call_with_retries(self._emit,
                                  max_retries=self.max_retries,
                                  _args=tuple((tag, timestamp, json_item)))
        else:
            call_with_retries(self.emit_frame_atonce,
                              max_retries=self.max_retries,
                              _args=tuple((tag, timestamp, frame)))
