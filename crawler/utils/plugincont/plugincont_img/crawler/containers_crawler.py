from containers import poll_containers, get_containers
import plugins_manager
from base_crawler import BaseCrawler, BaseFrame


class ContainerFrame(BaseFrame):

    def __init__(self, feature_types, container):
        BaseFrame.__init__(self, feature_types)
        self.metadata.update(container.get_metadata_dict())
        self.metadata['system_type'] = 'container'


class ContainersCrawler(BaseCrawler):

    def __init__(self,
                 features=['os', 'cpu'],
                 environment='cloudsight',
                 user_list='ALL',
                 host_namespace='',
                 plugin_places=['plugins'],
                 options={}):

        BaseCrawler.__init__(
            self,
            features=features,
            plugin_places=plugin_places,
            options=options)
        plugins_manager.reload_env_plugin(environment, plugin_places)
        plugins_manager.reload_container_crawl_plugins(
            features, plugin_places, options)
        self.plugins = plugins_manager.get_container_crawl_plugins(features)
        self.environment = environment
        self.host_namespace = host_namespace
        self.user_list = user_list

    def crawl_container(self, container, ignore_plugin_exception=True):
        """
        Crawls a specific container and returns a Frame for it.

        :param container: a Container object
        :param ignore_plugin_exception: just ignore exceptions in a plugin
        :return: a Frame object. The returned frame can have 0 features and
        still have metadata. This can occur if there were no plugins, or all
        the plugins raised an exception (and ignore_plugin_exception was True).
        """
        frame = ContainerFrame(self.features, container)
        for (plugin_obj, plugin_args) in self.plugins:
            try:
                frame.add_features(
                    plugin_obj.crawl(
                        container_id=container.long_id,
                        **plugin_args))
            except Exception as exc:
                if not ignore_plugin_exception:
                    raise exc
        return frame

    def polling_crawl(self, timeout, ignore_plugin_exception=True):
        """
        Crawls any container created before `timeout` seconds have elapsed.

        :param timeout: seconds to wait for new containers
        :param ignore_plugin_exception: just ignore exceptions in a plugin
        :return: a Frame object
        """
        container = poll_containers(
            timeout,
            user_list=self.user_list,
            host_namespace=self.host_namespace)
        if container:
            return self.crawl_container(container, ignore_plugin_exception)

        return None

    def crawl(self, ignore_plugin_exception=True):
        """
        Crawls all containers.

        :param ignore_plugin_exception: just ignore exceptions in a plugin
        :return: a list generator of Frame objects
        """
        containers_list = get_containers(
            user_list=self.user_list,
            host_namespace=self.host_namespace)
        for container in containers_list:
            yield self.crawl_container(container, ignore_plugin_exception)
