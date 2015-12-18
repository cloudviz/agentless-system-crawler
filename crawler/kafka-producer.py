#!/usr/bin/python
# -*- coding: utf-8 -*-
import pykafka
import kafka as kafka_python
import logging
import logging.handlers
import os
import errno
from functools import wraps
import time
import signal


def timeout(seconds=5, msg=os.strerror(errno.ETIMEDOUT)):

    def decorator(func):

        def timeout_handler(sig, frame):
            raise msg

        def wrapper(*args, **kwargs):
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(seconds)
            try:
                ret = func(*args, **kwargs)
            finally:
                signal.alarm(0)
            return ret

        return wraps(func)(wrapper)

    return decorator


@timeout(60)
def _publish_to_kafka_no_retries(fpath, url):

    try:
        list = url[len('kafka://'):].split('/')

        if len(list) == 2:
            kurl = list[0]
            topic = list[1]
        else:
            raise Exception(
                'The kafka url provided does not seem to be valid: %s. '
                'It should be something like this: '
                'kafka://[ip|hostname]:[port]/[kafka_topic]. '
                'For example: kafka://1.1.1.1:1234/alchemy_metrics' % url)

        kafka_python_client = kafka_python.KafkaClient(kurl)
        kafka_python_client.ensure_topic_exists(topic)

        kafka = pykafka.KafkaClient(hosts=kurl)
        publish_topic_object = kafka.topics[topic]
        producer = publish_topic_object.get_producer()

        with open(fpath, 'r') as fp:
            text = fp.read()
            producer.produce([text.strip()])
    except Exception as e:

        logger.debug('Could not send data to {0}: {1}'.format(url, e))
        raise


def publish_to_kafka(fpath, url, max_emit_retries=10):
    broker_alive = False
    retries = 0
    while not broker_alive and retries <= max_emit_retries:
        try:
            retries += 1
            _publish_to_kafka_no_retries(fpath, url)
            broker_alive = True
        except Exception:
            if retries <= max_emit_retries:

                # Wait for (2^retries * 100) milliseconds

                wait_time = 2.0 ** retries * 0.1
                logger.error(
                    'Could not connect to the kafka server at %s. Retry in '
                    '%f seconds.' % (url, wait_time))
                time.sleep(wait_time)
            else:
                raise


if __name__ == '__main__':

    import logging
    import sys

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    fh = logging.handlers.RotatingFileHandler(
        '/var/log/kafka-producer.log', maxBytes=2 << 27, backupCount=4)
    fh.setLevel(logging.INFO)
    logger.addHandler(fh)

    try:
        publish_to_kafka(sys.argv[1], sys.argv[2])
    except Exception as e:
        logger.error('kafka-producer gave up and could not send to kafka: %s'
                     % e)
        exit(1)
