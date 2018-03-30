#!/usr/bin/python
# -*- coding: utf-8 -*-
import logging

import plugins_manager
from base_crawler import BaseFrame
from utils.crawler_exceptions import EmitterUnsupportedProtocol

logger = logging.getLogger('crawlutils')


class EmittersManager:

    """
    Class that manages a list of formatter and emitter objects, one per url.
    The formatter takes a frame and writes it into an iostream, and the
    emitter takes the iostream and emits it.

    This class should be instantiated at the beginning of the program,
    and emit() should be called for each frame.
    """

    def __init__(
            self,
            urls,
            format='csv',
            compress=False,
            extra_metadata={},
            plugin_places=['plugins']
    ):
        """
        Initializes a list of emitter objects; also stores all the args.

        :param urls: list of URLs to send to
        :param format: format of each feature string
        :param compress: gzip each emitter frame or not
        :param extra_metadata: dict added to the metadata of each frame
        """
        self.extra_metadata = extra_metadata
        self.compress = compress

        # Create a list of Emitter objects based on urls
        self.emitter_plugins = plugins_manager.get_emitter_plugins(
            urls,
            format,
            plugin_places)
        if not self.emitter_plugins:
            raise EmitterUnsupportedProtocol('Emit protocols not supported')

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
        for (emitter_obj, emitter_args) in self.emitter_plugins:
            emitter_obj.emit(frame, self.compress,
                             metadata, snapshot_num, **(emitter_args or {}))
