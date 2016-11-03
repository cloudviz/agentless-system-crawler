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

    # apply per plugin configs
    crawlers = _config['crawlers']
    for feature in params['features']:
        for target in {'container', 'host', 'vm'}:
	    try:
		plugin = '%s_%s' % (feature, target)
		for arg in options[feature]:
		    crawlers[plugin] = {}
		    crawlers[plugin][arg] = options[feature][arg]
		if 'avoid_setns' in options:
		    crawlers[plugin]['avoid_setns'] = options['avoid_setns']
	    except KeyError as exc:
		logger.warning(
		    'Can not apply users --options configuration: %s' %
		    exc)


def get_config():
    global _config

    if not _config:
        parse_crawler_config()

    return _config
