from ConfigParser import SafeConfigParser
from yapsy.PluginManager import PluginManager
from crawler_exceptions import RuntimeEnvironmentPluginNotFound
from runtime_environment import IRuntimeEnvironment
from icrawl_plugin import IContainerCrawler, IVMCrawler, IHostCrawler
import misc
import defaults


# default runtime environment: cloudsigth and plugins in 'plugins/'
runtime_env = None

container_crawl_plugins = []
vm_crawl_plugins = []
host_crawl_plugins = []


def parse_crawler_config(crawler_config_place):
    config_parser = SafeConfigParser()
    crawler_config_place = misc.execution_path(crawler_config_place)
    crawler_config_files = {'global': 'global.conf',
                            'crawl_plugins': 'crawl_plugins.conf',
                            'emit_plugins': 'emit_plugins.conf'}
    crawl_plugins_file = crawler_config_place + \
        "/" + crawler_config_files.get('crawl_plugins')

    # reading only read plugins file for now
    config_parser.read(crawl_plugins_file)
    crawl_plugins = config_parser.sections()

    return (crawl_plugins, config_parser)


def _load_plugins(plugin_places=[misc.execution_path('plugins')],
                  crawler_config_place=misc.execution_path(
                      defaults.DEFAULT_CRAWLER_CONFIG_PLACE),
                  category_filter={},
                  filter_func=lambda *arg: True):
    pm = PluginManager(plugin_info_ext='plugin')

    # Normalize the paths to the location of this file.
    # XXX-ricarkol: there has to be a better way to do this.
    plugin_places = [misc.execution_path(x) for x in plugin_places]

    pm.setPluginPlaces(plugin_places)
    pm.setCategoriesFilter(category_filter)
    pm.collectPlugins()

    (enabled_plugins, plugins_options) = parse_crawler_config(
        crawler_config_place)

    for plugin in pm.getAllPlugins():
        if filter_func(plugin.plugin_object, plugin.name, enabled_plugins):
            plugin_args = {}
            if plugins_options.has_section(plugin.name):
                plugin_args = dict(plugins_options.items(plugin.name))
            yield (plugin.plugin_object, plugin_args)


def reload_env_plugin(plugin_places=[misc.execution_path('plugins')],
                      environment='cloudsight'):
    global runtime_env
    _plugins = list(
        _load_plugins(
            plugin_places,
            category_filter={"env": IRuntimeEnvironment},
            filter_func=lambda plugin, *unused:
            plugin.get_environment_name() == environment))

    try:
        (runtime_env, unused_args) = _plugins[0]

    except TypeError:
        raise RuntimeEnvironmentPluginNotFound('Could not find a valid "%s" '
                                               'environment plugin at %s' %
                                               (environment, plugin_places))

    return runtime_env


def get_runtime_env_plugin():
    global runtime_env
    if not runtime_env:
        runtime_env = reload_env_plugin()
    return runtime_env


def reload_container_crawl_plugins(
        plugin_places=[misc.execution_path('plugins')],
        crawler_config_place=misc.execution_path(
            defaults.DEFAULT_CRAWLER_CONFIG_PLACE),
        features=defaults.DEFAULT_FEATURES_TO_CRAWL,
        plugin_mode=defaults.DEFAULT_PLUGIN_MODE):
    global container_crawl_plugins

    # using --plugin_mode  to override plugins for legacy CLI based invocation

    if plugin_mode is False:  # aka override via --features CLI
        filter_func = lambda plugin_obj, plugin_name, enabled_plugins: (
            plugin_obj.get_feature() in features.split(','))
    else:
        filter_func = lambda plugin_obj, plugin_name, enabled_plugins: (
            plugin_name in enabled_plugins)

    container_crawl_plugins = list(
        _load_plugins(
            plugin_places + ['plugins'],
            crawler_config_place=crawler_config_place,
            category_filter={
                "crawler": IContainerCrawler},
            filter_func=filter_func))


def reload_vm_crawl_plugins(
        plugin_places=[misc.execution_path('plugins')],
        crawler_config_place=misc.execution_path(
            defaults.DEFAULT_CRAWLER_CONFIG_PLACE),
        features=defaults.DEFAULT_FEATURES_TO_CRAWL,
        plugin_mode=defaults.DEFAULT_PLUGIN_MODE):
    global vm_crawl_plugins

    if plugin_mode is False:  # aka override via --features CLI
        filter_func = lambda plugin_obj, plugin_name, enabled_plugins: (
            plugin_obj.get_feature() in features.split(','))
    else:
        filter_func = lambda plugin_obj, plugin_name, enabled_plugins: (
            plugin_name in enabled_plugins)

    vm_crawl_plugins = list(
        _load_plugins(
            plugin_places + ['plugins'],
            crawler_config_place=crawler_config_place,
            category_filter={
                "crawler": IVMCrawler},
            filter_func=filter_func))

    # Filtering of features is a temp fix.
    # TODO remove the filtering of features after we move all
    # features to be plugins.


def reload_host_crawl_plugins(
        plugin_places=[misc.execution_path('plugins')],
        crawler_config_place=misc.execution_path(
            defaults.DEFAULT_CRAWLER_CONFIG_PLACE),
        features=defaults.DEFAULT_FEATURES_TO_CRAWL,
        plugin_mode=defaults.DEFAULT_PLUGIN_MODE):
    global host_crawl_plugins

    if plugin_mode is False:  # aka override via --features CLI
        filter_func = lambda plugin_obj, plugin_name, enabled_plugins: (
            plugin_obj.get_feature() in features.split(','))
    else:
        filter_func = lambda plugin_obj, plugin_name, enabled_plugins: (
            plugin_name in enabled_plugins)

    host_crawl_plugins = list(
        _load_plugins(
            plugin_places + ['plugins'],
            crawler_config_place=crawler_config_place,
            category_filter={
                "crawler": IHostCrawler},
            filter_func=filter_func))
    # Filtering of features is a temp fix.
    # TODO remove the filtering of features after we move all
    # features to be plugins.


def get_container_crawl_plugins():
    global container_crawl_plugins
    return container_crawl_plugins


def get_vm_crawl_plugins():
    global vm_crawl_plugins
    return vm_crawl_plugins


def get_host_crawl_plugins():
    global host_crawl_plugins
    return host_crawl_plugins
