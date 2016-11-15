from configobj import ConfigObj
from validate import Validator
import logging
import misc

CONFIG_SPEC_PATH = 'config_spec_and_defaults.conf'

_config = None

logger = logging.getLogger('crawlutils')


def parse_crawler_config(config_path='crawler.conf'):
    global _config

    # 1. get configs
    _config = ConfigObj(infile=misc.execution_path(config_path),
                        configspec=misc.execution_path(CONFIG_SPEC_PATH))

    # Configspec is not being used currently
    # but keeping validate() and apply_user_args() for future.
    # Essentially NOP right now

    # 2. apply defaults
    vdt = Validator()
    _config.validate(vdt)


def apply_user_args(options={}, params={}):
    global _config

    try:
        # apply global configs
        if 'compress' in options:
            _config['general']['compress'] = options['compress']
    except KeyError as exc:
        logger.warning('Can not apply users --options configuration: %s' % exc)


def get_config():
    global _config

    if not _config:
        parse_crawler_config()

    return _config
