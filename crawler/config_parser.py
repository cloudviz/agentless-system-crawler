from configobj import ConfigObj
from validate import Validator
import misc

CONFIG_SPEC_PATH = 'config_spec_and_defaults.conf'

_config = None


def parse_crawler_config(config_path='crawler.conf'):
    global _config

    # 1. get configs
    _config = ConfigObj(infile=misc.execution_path(config_path),
                        configspec=misc.execution_path(CONFIG_SPEC_PATH))

    # 2. apply defaults
    vdt = Validator()
    _config.validate(vdt)


def apply_user_args(options={}):
    global _config

    # apply global configs
    if 'compress' in options:
        _config['general']['compress'] = options['compress']

    # apply per plugin configs
    crawlers = _config['crawlers']
    for plugin in crawlers:
        if 'avoid_setns' in options:
            crawlers[plugin]['avoid_setns'] = options['avoid_setns']

        feature = plugin.replace('_host', '').replace('_container', '')
        if feature in options:
            crawlers[plugin] = options[feature]


def get_config():
    global _config

    if not _config:
        parse_crawler_config()

    return _config
