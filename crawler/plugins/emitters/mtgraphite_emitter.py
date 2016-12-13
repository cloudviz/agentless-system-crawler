import logging

from plugins.emitters.base_emitter import BaseEmitter
from utils.mtgraphite import MTGraphiteClient

logger = logging.getLogger('crawlutils')


class MtGraphiteEmitter(BaseEmitter):

    def __init__(self, url, timeout=1, max_retries=5,
                 emit_per_line=True):
        BaseEmitter.__init__(self, url,
                             timeout=timeout,
                             max_retries=max_retries,
                             emit_per_line=emit_per_line)
        self.mtgraphite_client = MTGraphiteClient(self.url)

    def emit(self, iostream, compress=False,
             metadata={}, snapshot_num=0):
        """

        :param iostream: a CStringIO used to buffer the formatted features.
        :param compress:
        :param metadata:
        :param snapshot_num:
        :return:
        """
        if self.emit_per_line:
            iostream.seek(0)
            num = self.mtgraphite_client.send_messages(iostream.readlines())
        else:
            num = self.mtgraphite_client.send_messages([iostream.getvalue()])
        logger.debug('Pushed %d messages to mtgraphite queue' % num)
