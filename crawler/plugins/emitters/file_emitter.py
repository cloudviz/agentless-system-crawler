import gzip
import shutil

from plugins.emitters.base_emitter import BaseEmitter


class FileEmitter(BaseEmitter):
    """
    Emitter to file. This creates one file per frame. The file names
    are the ones in the url. For example: for file:///tmp/a the file for
    the first frame would be /tmp/a.0 for a host, and /tmp/a.xyz.0 for a
    container with id xyz.
    """

    def emit(self, iostream, compress=False,
             metadata={}, snapshot_num=0):
        """

        :param iostream: a CStringIO used to buffer the formatted features.
        :param compress:
        :param metadata:
        :param snapshot_num:
        :return:
        """
        output_path = self.url[len('file://'):]
        short_name = metadata.get('emit_shortname', None)
        if not short_name:
            file_suffix = str(snapshot_num)
        else:
            file_suffix = '{0}.{1}'.format(short_name, snapshot_num)
        output_path = '{0}.{1}'.format(output_path, file_suffix)
        output_path += '.gz' if compress else ''

        with open(output_path, 'w') as fd:
            if compress:
                gzip_file = gzip.GzipFile(fileobj=fd, mode='w')
                gzip_file.write(iostream.getvalue())
                gzip_file.close()
            else:
                iostream.seek(0)
                shutil.copyfileobj(iostream, fd)
