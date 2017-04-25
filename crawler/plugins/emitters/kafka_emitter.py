import logging

import kafka as kafka_python
import pykafka

from iemit_plugin import IEmitter
from utils.misc import (NullHandler, call_with_retries)

logger = logging.getLogger('crawlutils')
# Kafka logs too much
logging.getLogger('kafka').addHandler(NullHandler())


class KafkaEmitter(IEmitter):

    def get_emitter_protocol(self):
        return 'kafka'

    def init(self, url, timeout=1, max_retries=10, emit_format='csv'):
        IEmitter.init(self, url,
                      timeout=timeout,
                      max_retries=max_retries,
                      emit_format=emit_format)

        if emit_format == 'json':
            self.emit_per_line = True

        try:
            broker, topic = url[len('kafka://'):].split('/')
        except (KeyError, TypeError) as exc:
            logger.warn('Can not parse the url provided.')
            raise exc

        self.client = None
        self.producer = None

        call_with_retries(self.connect_to_broker,
                          max_retries=self.max_retries,
                          _args=tuple((broker, topic)))

    def connect_to_broker(self, broker, topic):
        kafka_python_client = kafka_python.SimpleClient(broker)
        kafka_python_client.ensure_topic_exists(topic)

        self.client = pykafka.KafkaClient(hosts=broker)
        self.producer = self.client.topics[topic].get_producer()

    def emit(self, frame, compress=False,
             metadata={}, snapshot_num=0, **kwargs):
        """

        :param compress:
        :param metadata:
        :param snapshot_num:
        :return:
        """
        iostream = self.format(frame)
        if compress:
            raise NotImplementedError('Compress not implemented.')

        if self.emit_per_line:
            iostream.seek(0)
            for line in iostream.readlines():
                call_with_retries(lambda io: self.producer.produce([line]),
                                  max_retries=self.max_retries,
                                  _args=tuple([iostream]))
        else:
            call_with_retries(
                lambda io: self.producer.produce([io.getvalue()]),
                max_retries=self.max_retries,
                _args=tuple([iostream]))
