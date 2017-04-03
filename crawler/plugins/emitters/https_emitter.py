import logging

from iemit_plugin import IEmitter
from plugins.emitters.base_http_emitter import BaseHttpEmitter

logger = logging.getLogger('crawlutils')


class HttpsEmitter(BaseHttpEmitter, IEmitter):

    def get_emitter_protocol(self):
        return 'https'
