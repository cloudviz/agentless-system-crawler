from utils.misc import enum

Modes = enum(INVM='INVM',
             OUTVM='OUTVM',
             MOUNTPOINT='MOUNTPOINT',
             OUTCONTAINER='OUTCONTAINER',
             MESOS='MESOS',
             K8S='K8S')
