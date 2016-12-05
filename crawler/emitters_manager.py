#!/usr/bin/python
# -*- coding: utf-8 -*-
import cStringIO
import logging
import urlparse

from base_crawler import BaseFrame
from formatters import (write_in_csv_format,
                        write_in_json_format,
                        write_in_graphite_format)
from crawler_exceptions import (EmitterUnsupportedFormat,
                                EmitterUnsupportedProtocol)
from plugins.emitters.file_emitter import FileEmitter
from plugins.emitters.http_emitter import HttpEmitter
from plugins.emitters.kafka_emitter import KafkaEmitter
from plugins.emitters.mtgraphite_emitter import MtGraphiteEmitter
from plugins.emitters.stdout_emitter import StdoutEmitter

logger = logging.getLogger('crawlutils')


class EmittersManager:
    """
    Class that manages a list of formatter and emitter objects, one per url.
    The formatter takes a frame and writes it into an iostream, and the
    emitter takes the iostream and emits it.

    This class should be instantiated at the beginning of the program,
    and emit() should be called for each frame.
    """

    """
    This maps url-protocols to emitters and formatters. For example,
    when writing to stdout in csv format, this should use the
    write_in_csv_format formatter and the StdoutEmitter.
    """
    proto_to_class = {
        'stdout': {'csv': {'class': StdoutEmitter, 'per_line': False,
                           'formatter': write_in_csv_format},
                   'graphite': {'class': StdoutEmitter, 'per_line': False,
                                'formatter': write_in_graphite_format},
                   'json': {'class': StdoutEmitter, 'per_line': False,
                            'formatter': write_in_json_format},
                   },
        'file': {'csv': {'class': FileEmitter, 'per_line': False,
                         'formatter': write_in_csv_format},
                 'graphite': {'class': FileEmitter, 'per_line': False,
                              'formatter': write_in_graphite_format},
                 'json': {'class': FileEmitter, 'per_line': False,
                          'formatter': write_in_json_format},
                 },
        'http': {'csv': {'class': HttpEmitter, 'per_line': False,
                         'formatter': write_in_csv_format},
                 'graphite': {'class': HttpEmitter, 'per_line': False,
                              'formatter': write_in_graphite_format},
                 'json': {'class': HttpEmitter, 'per_line': True,
                          'formatter': write_in_json_format},
                 },
        'kafka': {'csv': {'class': KafkaEmitter, 'per_line': False,
                          'formatter': write_in_csv_format},
                  'graphite': {'class': KafkaEmitter, 'per_line': False,
                               'formatter': write_in_graphite_format},
                  'json': {'class': KafkaEmitter, 'per_line': True,
                           'formatter': write_in_json_format},
                  },
        'mtgraphite': {'graphite': {'class': MtGraphiteEmitter,
                                    'per_line': True,
                                    'formatter': write_in_graphite_format},
                       },
    }

    def __init__(
            self,
            urls,
            format='csv',
            compress=False,
            extra_metadata={}
    ):
        """
        Initializes a list of emitter objects; also stores all the args.

        :param urls: list of URLs to send to
        :param format: format of each feature string
        :param compress: gzip each emitter frame or not
        :param extra_metadata: dict added to the metadata of each frame
        """
        self.extra_metadata = extra_metadata
        self.urls = urls
        self.compress = compress
        self.format = format

        # Create a list of Emitter objects based on the list of passed urls
        self.emitters = []
        for url in self.urls:
            self.allocate_emitter(url)

    def allocate_emitter(self, url):
        """
        Allocate a formatter and an emitter object based on the
        self.proto_to_class mapping. The formatter takes a frame and writes
        it into an iostream. The emitter takes the iostream and emits.

        :param url:
        :return:
        """
        parsed = urlparse.urlparse(url)
        proto = parsed.scheme
        if proto not in self.proto_to_class:
            raise EmitterUnsupportedProtocol('Not supported: %s' % proto)
        if self.format not in self.proto_to_class[proto]:
            raise EmitterUnsupportedFormat('Not supported: %s' % self.format)
        emitter_class = self.proto_to_class[proto][self.format]['class']
        emit_per_line = self.proto_to_class[proto][self.format]['per_line']
        emitter = emitter_class(url, emit_per_line=emit_per_line)
        formatter = self.proto_to_class[proto][self.format]['formatter']
        self.emitters.append((formatter, emitter))

    def emit(self, frame, snapshot_num=0):
        """
        Sends a frame to the URLs specified at __init__

        :param frame: frame of type BaseFrame
        :param snapshot_num: iteration count (from worker.py). This is just
        used to differentiate successive frame files (when url is file://).
        :return: None
        """
        if not isinstance(frame, BaseFrame):
            raise TypeError('frame is not of type BaseFrame')

        metadata = frame.metadata
        metadata.update(self.extra_metadata)

        iostream = cStringIO.StringIO()

        # Pass iostream to the emitters so they can sent its content to their
        # respective url
        for formatter, emitter in self.emitters:
            # this writes the frame metadata and data into iostream
            formatter(iostream, frame)
            # this emits the iostream data
            emitter.emit(iostream, self.compress,
                         metadata, snapshot_num)
