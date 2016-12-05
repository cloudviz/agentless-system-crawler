import logging
import kafka as kafka_python
import pykafka

try:
    from plugins.emitters.base_emitter import BaseEmitter
    from misc import (NullHandler, call_with_retries)
except ImportError:
    from crawler.plugins.emitters.base_emitter import BaseEmitter
    from crawler.misc import (NullHandler, call_with_retries)

logger = logging.getLogger('crawlutils')
# Kafka logs too much
logging.getLogger('kafka').addHandler(NullHandler())


class KafkaEmitter(BaseEmitter):

    def __init__(self, url, timeout=1, max_retries=10,
                 emit_per_line=False):
        BaseEmitter.__init__(self, url,
                             timeout=timeout,
                             max_retries=max_retries,
                             emit_per_line=emit_per_line)

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

    def emit(self, iostream, compress=False,
             metadata={}, snapshot_num=0):
        """

        :param iostream: a CStringIO used to buffer the formatted features.
        :param compress:
        :param metadata:
        :param snapshot_num:
        :return:
        """
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
