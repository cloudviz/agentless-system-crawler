from yapsy.PluginManager import PluginManager
from crawler_exceptions import RuntimeEnvironmentPluginNotFound
from runtime_environment import IRuntimeEnvironment
import misc


def load_env_plugin(plugin_places=[misc.execution_path('plugins')],
                    environment='cloudsight'):
    pm = PluginManager(plugin_info_ext='plugin')

    # Normalize the paths to the location of this file.
    # XXX-ricarkol: there has to be a better way to do this.
    plugin_places = [misc.execution_path(x) for x in plugin_places]

    pm.setPluginPlaces(plugin_places)
    pm.setCategoriesFilter({"RuntimeEnvironment": IRuntimeEnvironment})
    pm.collectPlugins()

    for env_plugin in pm.getAllPlugins():
        # There should be only one plugin of the given category and type;
        # but in case there are more, pick the first one.
        if env_plugin.plugin_object.get_environment_name() == environment:
            return env_plugin.plugin_object
    raise RuntimeEnvironmentPluginNotFound('Could not find a valid "%s" '
                                           'environment plugin at %s' %
                                           (environment, plugin_places))


def reload_env_plugin(plugin_places=[misc.execution_path('plugins')],
                      environment='cloudsight'):
    global runtime_env
    runtime_env = load_env_plugin(plugin_places, environment)

# default runtime environment: cloudsigth and plugins in 'plugins/'
runtime_env = load_env_plugin(plugin_places=[misc.execution_path('plugins')],
                              environment='cloudsight')


def get_runtime_env_plugin():
    global runtime_env
    return runtime_env
