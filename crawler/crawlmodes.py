from __future__ import absolute_import
from .utils.misc import enum

Modes = enum(INVM='INVM',
             OUTVM='OUTVM',
             MOUNTPOINT='MOUNTPOINT',
             OUTCONTAINER='OUTCONTAINER',
             MESOS='MESOS')
