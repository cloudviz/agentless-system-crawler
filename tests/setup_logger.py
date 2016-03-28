import logging
import os
import logging.handlers
import sys


def setup_logger(logger_name, logfile='crawler.log'):
    _logger = logging.getLogger(logger_name)
    _logger.setLevel(logging.INFO)
    logfile_name, logfile_xtnsion = os.path.splitext(logfile)
    fname = logfile
    h = logging.handlers.RotatingFileHandler(
            filename=fname, maxBytes=10e6, backupCount=1)
    f = logging.Formatter(
            '%(asctime)s %(processName)-10s %(levelname)-8s %(message)s')
    h.setFormatter(f)
    _logger.addHandler(h)


def setup_logger_stdout(logger_name):
    _logger = logging.getLogger(logger_name)
    _logger.setLevel(logging.DEBUG)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    _logger.addHandler(ch)
