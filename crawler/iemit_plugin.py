import cStringIO
from yapsy.IPlugin import IPlugin
from formatters import (write_in_csv_format,
                        write_in_json_format,
                        write_in_graphite_format,
                        write_in_logstash_format)
from utils.crawler_exceptions import (EmitterUnsupportedFormat)


class IEmitter(IPlugin):

    """
    Base emitter class from which emitters like FileEmitter, StdoutEmitter
    should inherit. The main idea is that all emitters get a url, and should
    implement an emit() function given an iostream (a buffer with the features
    to emit).
    """

    def init(self, url, timeout=1, max_retries=5, emit_format='csv'):
        self.url = url
        self.timeout = timeout
        self.max_retries = max_retries
        self.emit_per_line = False

        self.supported_formats = {'csv': write_in_csv_format,
                                  'graphite': write_in_graphite_format,
                                  'json': write_in_json_format,
                                  'logstash': write_in_logstash_format}

        if emit_format in self.supported_formats:
            self.formatter = self.supported_formats[emit_format]
        else:
            raise EmitterUnsupportedFormat('Not supported: %s' % emit_format)

    def get_emitter_protocol(self):
        raise NotImplementedError()

    def format(self, frame):
        # this writes the frame metadata and data into iostream
        # Pass iostream to the emitters so they can send its content to their
        # respective url
        iostream = cStringIO.StringIO()
        self.formatter(iostream, frame)
        return iostream

    def emit(self, frame, compress=False,
             metadata={}, snapshot_num=0, **kwargs):
        """

        :param iostream: a CStringIO used to buffer the formatted features.
        :param compress:
        :param metadata:
        :param snapshot_num:
        :return:
        """
        # this formats and emits an input frame
        raise NotImplementedError()
