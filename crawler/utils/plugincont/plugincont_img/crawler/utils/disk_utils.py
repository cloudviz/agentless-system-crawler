import psutil

from utils.features import DiskFeature


def crawl_disk_partitions():
    partitions = []
    for partition in psutil.disk_partitions(all=True):
        try:
            pdiskusage = psutil.disk_usage(partition.mountpoint)
            partitions.append((partition.mountpoint, DiskFeature(
                partition.device,
                100.0 - pdiskusage.percent,
                partition.fstype,
                partition.mountpoint,
                partition.opts,
                pdiskusage.total,
            ), 'disk'))
        except OSError:
            continue
    return partitions
