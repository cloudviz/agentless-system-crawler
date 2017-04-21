import cStringIO
import gzip
import sys

from iemit_plugin import IEmitter


class StdoutEmitter(IEmitter):

    def get_emitter_protocol(self):
        return 'stdout'

    def emit(self, frame, compress=False,
             metadata={}, snapshot_num=0, **kwargs):
        """

        :param iostream: a CStringIO used to buffer the formatted features.
        :param compress:
        :param metadata:
        :param snapshot_num:
        :return:
        """
        iostream = self.format(frame)
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
