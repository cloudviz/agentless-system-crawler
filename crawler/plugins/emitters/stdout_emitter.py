import cStringIO
import gzip
import sys

try:
    from plugins.emitters.base_emitter import BaseEmitter
except ImportError:
    from crawler.plugins.emitters.base_emitter import BaseEmitter


class StdoutEmitter(BaseEmitter):
    def __init__(self, url, timeout=1, max_retries=5,
                 emit_per_line=False):
        BaseEmitter.__init__(self, url,
                             timeout=timeout,
                             max_retries=max_retries,
                             emit_per_line=emit_per_line)

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
            for line in iostream.readlines():
                self.emit_string(line, compress)
        else:
            self.emit_string(iostream.getvalue().strip(), compress)

    def emit_string(self, string, compress):
        if compress:
            tempio = cStringIO.StringIO()
            gzip_file = gzip.GzipFile(fileobj=tempio, mode='w')
            gzip_file.write(string)
            gzip_file.close()
            print tempio.getvalue()
        else:
            print "%s" % string
        sys.stdout.flush()
