import logging

from yapsy.PluginManager import PluginManager
import urlparse
import config_parser
from icrawl_plugin import IContainerCrawler, IVMCrawler, IHostCrawler
from iemit_plugin import IEmitter
from runtime_environment import IRuntimeEnvironment
from utils import misc
from utils.crawler_exceptions import RuntimeEnvironmentPluginNotFound

logger = logging.getLogger('crawlutils')

# default runtime environment: cloudsigth and plugins in 'plugins/'
runtime_env = None

container_crawl_plugins = []
vm_crawl_plugins = []
host_crawl_plugins = []


# XXX make this a class

def get_plugins(
        category_filter={},
        plugin_places=['plugins']):

    pm = PluginManager(plugin_info_ext='plugin')

    # Normalize the paths to the location of this file.
    # XXX-ricarkol: there has to be a better way to do this.
    plugin_places = [misc.execution_path(x) for x in plugin_places]

    pm.setPluginPlaces(plugin_places)
    pm.setCategoriesFilter(category_filter)
    pm.collectPlugins()
    return pm.getAllPlugins()


def get_emitter_plugins(urls=['stdout://'],
                        format='csv',
                        plugin_places=['plugins']):
    category_filter = {"emitter": IEmitter}
    all_emitter_plugins = get_plugins(category_filter, plugin_places)
    selected_emitter_plugins = []
    for url in urls:
        parsed = urlparse.urlparse(url)
        proto = parsed.scheme
        for plugin in all_emitter_plugins:
            plugin_obj = plugin.plugin_object
            if plugin_obj.get_emitter_protocol() == proto:
                plugin_obj.init(url, emit_format=format)
                selected_emitter_plugins.append(plugin_obj)

        return selected_emitter_plugins


def reload_env_plugin(environment='cloudsight', plugin_places=['plugins']):
    global runtime_env

    category_filter = {"env": IRuntimeEnvironment}
    env_plugins = get_plugins(category_filter, plugin_places)

    for plugin in env_plugins:
        plugin_obj = plugin.plugin_object
        if plugin_obj.get_environment_name() == environment:
            runtime_env = plugin_obj
            break

    if runtime_env is None:
        raise RuntimeEnvironmentPluginNotFound('Could not find a valid "%s" '
                                               'environment plugin at %s' %
                                               (environment, plugin_places))
    return runtime_env


def get_runtime_env_plugin():
    global runtime_env
    if not runtime_env:
        runtime_env = reload_env_plugin()
    return runtime_env


def get_plugin_args(plugin, config, options):
    plugin_args = {}

    if plugin.name in config['crawlers']:
        plugin_args = config['crawlers'][plugin.name]
        if 'avoid_setns' in plugin_args:
            plugin_args['avoid_setns'] = plugin_args.as_bool('avoid_setns')

    is_feature_crawler = getattr(plugin.plugin_object, 'get_feature', None)
    if is_feature_crawler is not None:
        feature = plugin.plugin_object.get_feature()
        if feature in options:
            for arg in options[feature]:
                plugin_args[arg] = options[feature][arg]
        # the alternative: plugin_args = options.get(feature)
        # might overwrite options from crawler.conf

    try:
        if options['avoid_setns'] is True:
            plugin_args['avoid_setns'] = options['avoid_setns']
        if options['mountpoint'] != '/':
            plugin_args['root_dir'] = options['mountpoint']
    except KeyError as exc:
        logger.warning(
            'Can not apply users --options configuration: %s' % exc)

    return plugin_args


def load_crawl_plugins(
        category_filter={},
        features=['os', 'cpu'],
        plugin_places=['plugins'],
        options={}):

    crawl_plugins = get_plugins(category_filter, plugin_places)
    config = config_parser.get_config()

    enabled_plugins = []
    if 'enabled_plugins' in config['general']:
        enabled_plugins = config['general']['enabled_plugins']
        if 'ALL' in enabled_plugins:
            enabled_plugins = [p for p in config['crawlers']]
            # Reading from 'crawlers' section inside crawler.conf
            # Alternatively, 'ALL' can be made to signify
            # all crawlers in plugins/*

    for plugin in crawl_plugins:
        if ((plugin.name in enabled_plugins) or (
                plugin.plugin_object.get_feature() in features)):
            plugin_args = get_plugin_args(plugin, config, options)
            yield (plugin.plugin_object, plugin_args)


def reload_container_crawl_plugins(
        features=['os', 'cpu'],
        plugin_places=['plugins'],
        options={}):
    global container_crawl_plugins

    container_crawl_plugins = list(
        load_crawl_plugins(
            category_filter={
                "crawler": IContainerCrawler},
            features=features,
            plugin_places=plugin_places,
            options=options))


def reload_vm_crawl_plugins(
        features=['os', 'cpu'],
        plugin_places=['plugins'],
        options={}):
    global vm_crawl_plugins

    vm_crawl_plugins = list(
        load_crawl_plugins(
            category_filter={
                "crawler": IVMCrawler},
            features=features,
            plugin_places=plugin_places,
            options=options))


def reload_host_crawl_plugins(
        features=['os', 'cpu'],
        plugin_places=['plugins'],
        options={}):
    global host_crawl_plugins

    host_crawl_plugins = list(
        load_crawl_plugins(
            category_filter={
                "crawler": IHostCrawler},
            features=features,
            plugin_places=plugin_places,
            options=options))


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
