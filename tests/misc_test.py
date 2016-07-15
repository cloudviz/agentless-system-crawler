import crawler.misc


def test_find_mount_point(tmpdir):
    print(tmpdir)
    print(crawler.misc.find_mount_point(str(tmpdir)))
