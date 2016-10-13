import codecs
import fnmatch
import re
import logging
import os
import misc
from features import ConfigFeature

logger = logging.getLogger('crawlutils')


def crawl_config_files(
    root_dir='/',
    exclude_dirs=[],
    root_dir_alias=None,
    known_config_files=[],
    discover_config_files=False,
    accessed_since=0
):

    saved_args = locals()
    logger.debug('Crawling config files: %s' % (saved_args))

    assert os.path.isdir(root_dir)

    root_dir_alias = root_dir_alias or root_dir
    exclude_dirs = [misc.join_abs_paths(root_dir, d) for d in
                    exclude_dirs]
    exclude_regex = r'|'.join([fnmatch.translate(d) for d in
                               exclude_dirs]) or r'$.'
    known_config_files[:] = [misc.join_abs_paths(root_dir, f) for f in
                             known_config_files]
    known_config_files[:] = [f for f in known_config_files
                             if not re.match(exclude_regex, f)]
    config_file_set = set()
    for fpath in known_config_files:
        if os.path.exists(fpath):
            lstat = os.lstat(fpath)
            if (lstat.st_atime > accessed_since or
                    lstat.st_ctime > accessed_since):
                config_file_set.add(fpath)

    if discover_config_files:

        # Walk the directory hierarchy starting at 'root_dir' in BFS
        # order looking for config files.

        for (root_dirpath, dirs, files) in os.walk(root_dir):
            dirs[:] = [os.path.join(root_dirpath, d) for d in
                       dirs]
            dirs[:] = [d for d in dirs
                       if not re.match(exclude_regex, d)]
            files = [os.path.join(root_dirpath, f) for f in
                     files]
            files = [f for f in files
                     if not re.match(exclude_regex, f)]
            for fpath in files:
                if os.path.exists(fpath) \
                        and _is_config_file(fpath):
                    lstat = os.lstat(fpath)
                    if lstat.st_atime > accessed_since \
                            or lstat.st_ctime > accessed_since:
                        config_file_set.add(fpath)

    for fpath in config_file_set:
        (_, fname) = os.path.split(fpath)
        frelpath = fpath.replace(root_dir, root_dir_alias,
                                 1)  # root_dir relative path
        with codecs.open(filename=fpath, mode='r',
                         encoding='utf-8', errors='ignore') as \
                config_file:

            # Encode the contents of config_file as utf-8.

            yield (frelpath, ConfigFeature(fname,
                                           config_file.read(),
                                           frelpath), 'config')


def _is_config_file(fpath):
    (_, ext) = os.path.splitext(fpath)
    if os.path.isfile(fpath) and ext in [
        '.xml',
        '.ini',
        '.properties',
        '.conf',
        '.cnf',
        '.cfg',
        '.cf',
        '.config',
        '.allow',
        '.deny',
        '.lst',
    ] and os.path.getsize(fpath) <= 204800:
        return True
    return False
