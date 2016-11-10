from yapsy.PluginManager import PluginManager
from crawler_exceptions import RuntimeEnvironmentPluginNotFound
from runtime_environment import IRuntimeEnvironment
from icrawl_plugin import IContainerCrawler, IVMCrawler, IHostCrawler
import misc
import config_parser
import logging

logger = logging.getLogger('crawlutils')

# default runtime environment: cloudsigth and plugins in 'plugins/'
runtime_env = None

container_crawl_plugins = []
vm_crawl_plugins = []
host_crawl_plugins = []


def get_plugin_args(plugin, config, options):
    plugin_args = {}
    if plugin.name in config['crawlers']:
        try:
            plugin_args = config['crawlers'][plugin.name]
            plugin_args['avoid_setns'] = options['avoid_setns']
            plugin_args['avoid_setns'] = plugin_args.as_bool('avoid_setns')
            plugin_args['root_dir'] = options['mountpoint']
            feature = plugin.plugin_object.get_feature()
            if feature in options:
                for arg in options[feature]:
                    plugin_args[arg] = options[feature][arg]
        except KeyError as exc:
            logger.warning(
                'Can not apply users --options configuration: %s' % exc)
    return plugin_args


def _load_plugins(
        category_filter={},
        filter_func=lambda *arg: True,
        features=config_parser.get_config()['general']['features_to_crawl'],
        options={}):

    pm = PluginManager(plugin_info_ext='plugin')

    plugin_places = options.get(
        'plugin_places',
        config_parser.get_config()['general']['plugin_places'])

    # Normalize the paths to the location of this file.
    # XXX-ricarkol: there has to be a better way to do this.
    plugin_places = [misc.execution_path(x) for x in plugin_places]

    pm.setPluginPlaces(plugin_places)
    pm.setCategoriesFilter(category_filter)
    pm.collectPlugins()

    config = config_parser.get_config()
    enabled_plugins = [p for p in config['crawlers']]

    for plugin in pm.getAllPlugins():
        if filter_func(
                plugin.plugin_object,
                plugin.name,
                enabled_plugins,
                features):
            plugin_args = get_plugin_args(plugin, config, options)
            yield (plugin.plugin_object, plugin_args)


def reload_env_plugin(options={}):
    global runtime_env

    environment = options.get(
        'environment',
        config_parser.get_config()['general']['environment'])

    _plugins = list(
        _load_plugins(
            category_filter={"env": IRuntimeEnvironment},
            filter_func=lambda plugin, *unused:
            plugin.get_environment_name() == environment))

    try:
        (runtime_env, unused_args) = _plugins[0]
    except (TypeError, IndexError):
        plugin_places = options.get(
            'plugin_places',
            config_parser.get_config()['general']['plugin_places'])
        raise RuntimeEnvironmentPluginNotFound('Could not find a valid "%s" '
                                               'environment plugin at %s' %
                                               (environment, plugin_places))

    return runtime_env


def get_runtime_env_plugin():
    global runtime_env
    if not runtime_env:
        runtime_env = reload_env_plugin()
    return runtime_env


def plugin_filter_with_plugin_mode(
        plugin_obj,
        plugin_name,
        enabled_plugins,
        features):
    return (plugin_obj.get_feature() in features)


def plugin_filter_without_plugin_mode(
        plugin_obj,
        plugin_name,
        enabled_plugins,
        features):
    return (plugin_name in enabled_plugins)


def reload_container_crawl_plugins(
        features=config_parser.get_config()['general']['features_to_crawl'],
        options={}):
    global container_crawl_plugins
    plugin_mode = config_parser.get_config()['general']['plugin_mode']

    # using --plugin_mode  to override plugins for legacy CLI based invocation

    if plugin_mode is False:  # aka override via --features CLI
        filter_func = plugin_filter_with_plugin_mode
    else:
        filter_func = plugin_filter_without_plugin_mode

    container_crawl_plugins = list(
        _load_plugins(
            category_filter={
                "crawler": IContainerCrawler},
            filter_func=filter_func,
            features=features,
            options=options))


def reload_vm_crawl_plugins(
        features=config_parser.get_config()['general']['features_to_crawl'],
        options={}):
    global vm_crawl_plugins
    plugin_mode = config_parser.get_config()['general']['plugin_mode']

    if plugin_mode is False:  # aka override via --features CLI
        filter_func = plugin_filter_with_plugin_mode
    else:
        filter_func = plugin_filter_without_plugin_mode

    vm_crawl_plugins = list(
        _load_plugins(
            category_filter={
                "crawler": IVMCrawler},
            filter_func=filter_func,
            features=features,
            options=options))

    # Filtering of features is a temp fix.
    # TODO remove the filtering of features after we move all
    # features to be plugins.


def reload_host_crawl_plugins(
        features=config_parser.get_config()['general']['features_to_crawl'],
        options={}):
    global host_crawl_plugins
    plugin_mode = config_parser.get_config()['general']['plugin_mode']

    if plugin_mode is False:  # aka override via --features CLI
        filter_func = plugin_filter_with_plugin_mode
    else:
        filter_func = plugin_filter_without_plugin_mode

    host_crawl_plugins = list(
        _load_plugins(
            category_filter={
                "crawler": IHostCrawler},
            filter_func=filter_func,
            features=features,
            options=options))
    # Filtering of features is a temp fix.
    # TODO remove the filtering of features after we move all
    # features to be plugins.


def get_container_crawl_plugins(
    features=[
        'package',
        'os',
        'process',
        'file',
        'config']):
    global container_crawl_plugins
    if not container_crawl_plugins:
        reload_container_crawl_plugins(features=features)
    return container_crawl_plugins


def get_vm_crawl_plugins(
    features=[
        'package',
        'os',
        'process',
        'file',
        'config']):
    global vm_crawl_plugins
    if not vm_crawl_plugins:
        reload_vm_crawl_plugins(features=features)
    return vm_crawl_plugins


def get_host_crawl_plugins(
    features=[
        'package',
        'os',
        'process',
        'file',
        'config']):
    global host_crawl_plugins
    if not host_crawl_plugins:
        reload_host_crawl_plugins(features=features)
    return host_crawl_plugins
