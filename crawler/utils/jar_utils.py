import fnmatch
import logging
import os
import re
import hashlib
import zipfile

from utils.features import JarFeature

logger = logging.getLogger('crawlutils')


def crawl_jar_files(
        root_dir='/',
        exclude_dirs=[],
        root_dir_alias=None,
        accessed_since=0):

    if not os.path.isdir(root_dir):
        return

    saved_args = locals()
    logger.debug('crawl_jar_files: %s' % (saved_args))

    assert os.path.isdir(root_dir)
    if root_dir_alias is None:
        root_dir_alias = root_dir
    exclude_dirs = [os.path.join(root_dir, d) for d in
                    exclude_dirs]
    exclude_regex = r'|'.join([fnmatch.translate(d)
                               for d in exclude_dirs]) or r'$.'

    # walk the directory hierarchy starting at 'root_dir' in BFS
    # order

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
            if not fpath.endswith('.jar'):
                continue
            feature = _crawl_jar_file(root_dir, fpath,root_dir_alias)
            if feature:
                yield (feature.path, feature, 'jar')


# crawl a single file
def _crawl_jar_file(
    root_dir,
    fpath,
    root_dir_alias,
):
    if not fpath.endswith('.jar'):
        return

    hashes = []
    with zipfile.ZipFile(fpath, 'r') as zf:
        for info in zf.infolist():
            if not info.filename.endswith('.class'):
                continue
            data = zf.read(info.filename)
            md = hashlib.md5()
            md.update(data)
            hashes.append(md.hexdigest())

    # compute hash of jar file
    with open(fpath, 'rb') as jarin:
        md = hashlib.md5()
        md.update(jarin.read())
        jarhash = md.hexdigest()
    # This replaces `/<root_dir>/a/b/c` with `/<root_dir_alias>/a/b/c`
    frelpath = os.path.join(root_dir_alias,
                            os.path.relpath(fpath, root_dir))

    # This converts something like `/.` to `/`

    frelpath = os.path.normpath(frelpath)

    (_, fname) = os.path.split(frelpath)
    return JarFeature(
        os.path.basename(fpath),
        fpath,
        jarhash,
        hashes
        )
