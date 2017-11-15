#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import
import logging
import socket
import ssl
import struct
import time
import re

from .crawler_exceptions import MTGraphiteInvalidTenant

# This code is based upon the Kafka producer/client classes

logger = logging.getLogger('crawlutils')

DEFAULT_SOCKET_TIMEOUT_SECONDS = 120


class MTGraphiteClient(object):

    """
    xxx
    """

    def __init__(
        self,
        host_url,
        batch_send_every_t=5,
        batch_send_every_n=1000,
    ):
        self.host_url = host_url

        # A MTGraphite URL should look like:
        #  mtgraphite://<host>:<port>/<tenant>:<password>

        regex = re.compile(
            r'^mtgraphite://([^:/]+):([^:/]+)/([^:/]+):([^:/]+)$')
        if not regex.match(host_url):
            raise ValueError('The MTGraphite URL is invalid. It should be:'
                             ' mtgraphite://<host>:<port>/<tenant>:<pass>')

        matches = regex.search(host_url)
        self.host = matches.group(1)
        self.port = matches.group(2)
        self.tenant = matches.group(3)
        self.password = matches.group(4)

        # create a connection only when we need it, but keep it alive

        self.conn = None
        self.socket = None
        self.batch_send_every_n = batch_send_every_n
        self.batch_send_every_t = batch_send_every_t
        self.msgset = []
        self.next_timeout = time.time() + batch_send_every_t

    #
    # Private API  #
    #

    def _create_identification_message(self, self_identifier):
        identification_message = """"""
        identification_message += '1I'
        identification_message += chr(len(self_identifier))
        identification_message += self_identifier
        return identification_message

    def _create_authentication_msg(
        self,
        tenant,
        password,
            supertenant=True):
        authentication_message = """"""
        if supertenant:
            authentication_message += '2S'
        else:
            authentication_message += '2T'
        authentication_message += chr(len(tenant))
        authentication_message += tenant
        authentication_message += \
            chr(len(password))
        authentication_message += password
        return authentication_message

    def _send_and_check_identification_message(self, identification_message):
        identification_message_sent = self.conn.write(identification_message)

        if identification_message_sent != len(identification_message):
            logger.warning(
                'Identification message not sent properly, returned '
                'len = %d', identification_message_sent)
            return False
        else:
            return True

    def _send_and_check_authentication_message(self, authentication_message):
        authentication_message_sent = self.conn.write(authentication_message)
        logger.info(
            'Sent authentication with mtgraphite, returned length = '
            '%d' % authentication_message_sent)
        if authentication_message_sent != len(authentication_message):
            raise RuntimeError('failed to send tenant/password')
        chunk = self.conn.read(6)  # Expecting "1A"
        code = bytearray(chunk)[:2]

        logger.info('MTGraphite authentication server response of %s'
                    % code)
        if code == '0A':
            raise MTGraphiteInvalidTenant('Invalid password')

    def _get_socket(self):
        '''Get or create a connection to a broker using host and port'''
        if self.conn is not None:
            return self.conn

        logger.debug('Creating a new socket with _get_socket()')
        while self.conn is None:
            try:
                self.sequence = 1  # start with 1 as last_ack = 0
                self.socket = socket.socket(socket.AF_INET,
                                            socket.SOCK_STREAM)
                self.socket.settimeout(DEFAULT_SOCKET_TIMEOUT_SECONDS)
                self.conn = ssl.wrap_socket(self.socket,
                                            cert_reqs=ssl.CERT_NONE)
                self.conn.connect((self.host, int(self.port)))

                # We send this identifier message so that the server-side can
                # identify this specific crawler in the logs (its behind
                # load-balancer so it never sees our source-ip without this).

                self_identifier = str(self.conn.getsockname()[0])
                logger.debug('self_identifier = %s', self_identifier)
                identification_message = self._create_identification_message(
                    self_identifier)
                self._send_and_check_identification_message(
                    identification_message)

                msg = self._create_authentication_msg(self.tenant,
                                                      self.password,
                                                      supertenant=False)
                # We first try with a super tenant account.
                try:
                    self._send_and_check_authentication_message(msg)
                except Exception as e:
                    logger.info("Attempting to log in as tenant")
                    msg = self._create_authentication_msg(self.tenant,
                                                          self.password,
                                                          supertenant=False)
                    self._send_and_check_authentication_message(msg)
                return self.conn

            except Exception as e:
                logger.exception(e)
                if self.conn:
                    self.conn.close()
                    self.conn = None
                time.sleep(2)  # sleep for 2 seconds for now
                raise e

    def _write_messages_no_retries(self, msgset):
        s = self._get_socket()
        messages_string = bytearray('1W')
        messages_string.extend(bytearray(struct.pack('!I',
                                                     len(msgset))))
        for m in msgset:
            if m == msgset[0]:

                # logger.debug the first message

                logger.debug(m.strip())
            messages_string.extend('1M')
            messages_string.extend(bytearray(struct.pack('!I',
                                                         self.sequence)))
            messages_string.extend(bytearray(struct.pack('!I', len(m))))
            messages_string.extend(m)
            self.sequence += 1
        len_to_send = len(messages_string)
        len_sent = 0
        while len_sent < len_to_send:
            t = time.time() * 1000
            logger.debug(
                'About to write to the socket (already sent %d out of %d '
                'bytes)' % (len_sent, len_to_send))
            written = s.write(buffer(messages_string, len_sent))
            write_time = time.time() * 1000 - t
            logger.debug('Written %d bytes to socket in %f ms'
                         % (written, write_time))
            if written == 0:
                raise RuntimeError('socket connection broken')
                self.close()
                return False
            len_sent += written
        logger.debug('Waiting for response from mtgraphite server')
        chunk = s.read(6)  # Expecting "1A"+4byte_num_of_metrics_received
        code = bytearray(chunk)[:2]
        logger.debug('MTGraphite server response of %s'
                     % bytearray(chunk).strip())
        if code == '1A':
            logger.info('Confirmed write to mtgraphite socket.')
        return True

    def _write_messages(self, msgset, max_emit_retries=10):
        msg_sent = False
        retries = 0
        while not msg_sent and retries <= max_emit_retries:
            try:
                retries += 1
                self._write_messages_no_retries(msgset)
                msg_sent = True
            except Exception:
                if retries <= max_emit_retries:

                    # Wait for (2^retries * 100) milliseconds

                    wait_time = 2.0 ** retries * 0.1
                    logger.error(
                        'Could not connect to the mtgraphite server.Retry in '
                        '%f seconds.' % wait_time)

                    # The connection will be created again by
                    # _write_messages_no_retries().

                    self.close()
                    time.sleep(wait_time)
                else:
                    logger.error('Bail out on sending to mtgraphite server'
                                 )
                    raise

    #
    # Public API  #
    #

    def close(self):
        if self.conn:
            try:
                self.conn.close()
            except Exception as e:
                logger.exception(e)
            self.conn = None

    def send_messages(self, messages):
        """
        Helper method to send produce requests
        @param: *messages, one or more message payloads -- type str
        @returns: # of messages sent
        raises on error
        """

        # Guarantee that messages is actually a list or tuple (should always be
        # true)

        if not isinstance(messages, (list, tuple)):
            raise TypeError('messages is not a list or tuple!')

        # Raise TypeError if any message is not encoded as a str

        for m in messages:
            if not isinstance(m, str):
                raise TypeError('all produce message payloads must be type str'
                                )

        logger.debug("""""")
        logger.debug('New message:')
        logger.debug('len(msgset)=%d, batch_every_n=%d, time=%d, '
                     'next_timeout=%d' % (len(self.msgset),
                                          self.batch_send_every_n,
                                          time.time(),
                                          self.next_timeout))
        if messages:
            self.msgset.extend(messages)
        if len(self.msgset) >= self.batch_send_every_n or time.time() \
                > self.next_timeout:
            self._write_messages(self.msgset)
            self.msgset = []
            self.next_timeout = time.time() + self.batch_send_every_t

        return len(messages)

    def construct_message(self, space_id, group_id, metric_type, value,
                          timestamp=None):
        """
        Message constructor. Creates a message that you can then append to a
        list and send using send_messages.

        params:
        :param string space_id: space id (you can get this via logmet)
        :param string group_id: group id to access the metric
        :param string metric_type: type of metric (e.g., cpu, memory)
        :param int value: value of the metric
        :param int timestamp: None by default. If left as None, the current
                              time is used instead.

        returns: a string that contains the message you want to send.
        """
        return '%s.%s.%s %d %d\r\n' % (space_id, group_id, metric_type,
                                       value, timestamp or int(time.time()))
