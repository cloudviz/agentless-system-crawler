import logging

from iemit_plugin import IEmitter
from utils.mtgraphite import MTGraphiteClient
from formatters import write_in_graphite_format
from utils.crawler_exceptions import EmitterUnsupportedFormat

logger = logging.getLogger('crawlutils')


class MtGraphiteEmitter(IEmitter):

    def get_emitter_protocol(self):
        return 'mtgraphite'

    def init(self, url, timeout=1, max_retries=5, emit_format='graphite'):
        self.url = url
        self.timeout = timeout
        self.max_retries = max_retries
        self.emit_per_line = True

        if emit_format != 'graphite':
            raise EmitterUnsupportedFormat('Not supported: %s' % emit_format)

        self.formatter = write_in_graphite_format
        self.mtgraphite_client = MTGraphiteClient(self.url)

    def emit(self, frame, compress=False,
             metadata={}, snapshot_num=0, **kwargs):
        """

        :param compress:
        :param metadata:
        :param snapshot_num:
        :return:
        """
        iostream = self.format(frame)
        if self.emit_per_line:
            iostream.seek(0)
            num = self.mtgraphite_client.send_messages(iostream.readlines())
        else:
            num = self.mtgraphite_client.send_messages([iostream.getvalue()])
        logger.debug('Pushed %d messages to mtgraphite queue' % num)
