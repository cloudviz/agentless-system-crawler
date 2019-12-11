import logging
import os
import re
import stat

from utils.features import FileFeature

logger = logging.getLogger('crawlutils')


def crawl_files(
        root_dir='/',
        exclude_dirs=[],
        root_dir_alias=None,
        accessed_since=0):

    if not os.path.isdir(root_dir):
        return

    saved_args = locals()
    logger.debug('crawl_files: %s' % (saved_args))

    assert os.path.isdir(root_dir)
    if root_dir_alias is None:
        root_dir_alias = root_dir
    exclude_dirs = [os.path.join(root_dir, d) for d in
                    exclude_dirs]
    exclude_regex = re.compile(r'|'.join([d for d in exclude_dirs]))

    # walk the directory hierarchy starting at 'root_dir' in BFS
    # order

    feature = _crawl_file(root_dir, root_dir,
                          root_dir_alias)
    if feature and (feature.ctime > accessed_since or
                    feature.atime > accessed_since):
        yield (feature.path, feature, 'file')
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
            feature = _crawl_file(root_dir, fpath,
                                  root_dir_alias)
            if feature and (feature.ctime > accessed_since or
                            feature.atime > accessed_since):
                yield (feature.path, feature, 'file')
        for fpath in dirs:
            feature = _crawl_file(root_dir, fpath,
                                  root_dir_alias)
            if feature and (feature.ctime > accessed_since or
                            feature.atime > accessed_since):
                yield (feature.path, feature, 'file')


def _filetype(fpath, fperm):
    modebit = fperm[0]
    ftype = {
        'l': 'link',
        '-': 'file',
        'b': 'block',
        'd': 'dir',
        'c': 'char',
        'p': 'pipe',
    }.get(modebit)
    return ftype


_filemode_table = (
    (
        (stat.S_IFLNK, 'l'),
        (stat.S_IFREG, '-'),
        (stat.S_IFBLK, 'b'),
        (stat.S_IFDIR, 'd'),
        (stat.S_IFCHR, 'c'),
        (stat.S_IFIFO, 'p'),
    ),
    ((stat.S_IRUSR, 'r'), ),
    ((stat.S_IWUSR, 'w'), ),
    ((stat.S_IXUSR | stat.S_ISUID, 's'), (stat.S_ISUID, 'S'),
     (stat.S_IXUSR, 'x')),
    ((stat.S_IRGRP, 'r'), ),
    ((stat.S_IWGRP, 'w'), ),
    ((stat.S_IXGRP | stat.S_ISGID, 's'), (stat.S_ISGID, 'S'),
     (stat.S_IXGRP, 'x')),
    ((stat.S_IROTH, 'r'), ),
    ((stat.S_IWOTH, 'w'), ),
    ((stat.S_IXOTH | stat.S_ISVTX, 't'), (stat.S_ISVTX, 'T'),
     (stat.S_IXOTH, 'x')),
)


def _fileperm(mode):

    # Convert a file's mode to a string of the form '-rwxrwxrwx'

    perm = []
    for table in _filemode_table:
        for (bit, char) in table:
            if mode & bit == bit:
                perm.append(char)
                break
        else:
            perm.append('-')
    return ''.join(perm)


def _is_executable(fpath):
    return os.access(fpath, os.X_OK)

# crawl a single file


def _crawl_file(
    root_dir,
    fpath,
    root_dir_alias,
):
    lstat = os.lstat(fpath)
    fmode = lstat.st_mode
    fperm = _fileperm(fmode)
    ftype = _filetype(fpath, fperm)
    flinksto = None
    if ftype == 'link':
        try:

            # This has to be an absolute path, not a root-relative path

            flinksto = os.readlink(fpath)
        except:
            logger.error('Error reading linksto info for file %s'
                         % fpath, exc_info=True)
    fgroup = lstat.st_gid
    fuser = lstat.st_uid

    # This replaces `/<root_dir>/a/b/c` with `/<root_dir_alias>/a/b/c`

    frelpath = os.path.join(root_dir_alias,
                            os.path.relpath(fpath, root_dir))

    # This converts something like `/.` to `/`

    frelpath = os.path.normpath(frelpath)

    (_, fname) = os.path.split(frelpath)
    return FileFeature(
        lstat.st_atime,
        lstat.st_ctime,
        fgroup,
        flinksto,
        fmode,
        lstat.st_mtime,
        fname,
        frelpath,
        lstat.st_size,
        ftype,
        fuser,
    )
