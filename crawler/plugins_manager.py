from yapsy.PluginManager import PluginManager
from crawler_exceptions import RuntimeEnvironmentPluginNotFound
from runtime_environment import IRuntimeEnvironment
from icrawl_plugin import IContainerCrawler
import misc

# default runtime environment: cloudsigth and plugins in 'plugins/'
runtime_env = None

container_crawl_plugins = []


def _load_plugins(plugin_places=[misc.execution_path('plugins')],
                  category_filter={},
                  filter_func=lambda *arg: True):
    pm = PluginManager(plugin_info_ext='plugin')

    # Normalize the paths to the location of this file.
    # XXX-ricarkol: there has to be a better way to do this.
    plugin_places = [misc.execution_path(x) for x in plugin_places]

    pm.setPluginPlaces(plugin_places)
    pm.setCategoriesFilter(category_filter)
    pm.collectPlugins()

    for env_plugin in pm.getAllPlugins():
        if filter_func(env_plugin.plugin_object):
            yield env_plugin.plugin_object


def reload_env_plugin(plugin_places=[misc.execution_path('plugins')],
                      environment='cloudsight'):
    global runtime_env
    _plugins = _load_plugins(plugin_places,
                             category_filter={"env": IRuntimeEnvironment},
                             filter_func=lambda plugin:
                             plugin.get_environment_name() == environment)

    try:
        runtime_env = list(_plugins)[0]
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
        features='os'):
    global container_crawl_plugins
    container_crawl_plugins = list(
        _load_plugins(
            plugin_places,
            category_filter={
                "crawler": IContainerCrawler},
            filter_func=lambda plugin:
            plugin.get_feature() in features.split(',')))
    # Filtering of features is a temp fix.
    # TODO remove the filtering of features after we move all
    # features to be plugins.


def get_container_crawl_plugins():
    global container_crawl_plugins
    return container_crawl_plugins
