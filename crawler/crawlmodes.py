from utils.misc import enum

Modes = enum(INVM='INVM',
             OUTVM='OUTVM',
             MOUNTPOINT='MOUNTPOINT',
             OUTCONTAINER='OUTCONTAINER',
             OUTCONTAINERSAFE='OUTCONTAINERSAFE',
             MESOS='MESOS')
