from k8s_client import KubernetesClient
import plugins_manager
from base_crawler import BaseCrawler, BaseFrame


class PodFrame(BaseFrame):

    def __init__(self, feature_types, pod):
        BaseFrame.__init__(self, feature_types)
        # TODO: add additional k8s special metadata if needed
        # self.metadata.update(pod.get_metadata_dict())
        self.metadata['system_type'] = 'kubernetes'


class PodsCrawler(BaseCrawler):

    def __init__(self,
                 features=['os', 'cpu'],
                 environment='kubernetes',
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
        plugins_manager.reload_pod_crawl_plugins(
            features, plugin_places, options)
        self.plugins = plugins_manager.get_pod_crawl_plugins(features)
        self.environment = environment
        self.host_namespace = host_namespace
        self.user_list = user_list
        self.k8s_client = KubernetesClient()

    def _crawl_pod(self, pod, ignore_plugin_exception=True):
        frame = PodFrame(self.features, pod)
        for (plugin_obj, plugin_args) in self.plugins:
            try:
                frame.add_features(
                    plugin_obj.crawl(pod, **plugin_args))
            except Exception as exc:
                if not ignore_plugin_exception:
                    raise exc
        return frame

    def crawl(self, ignore_plugin_exception=True):
        for pod in self.k8s_client.list_all_pods():
            yield self._crawl_pod(pod, ignore_plugin_exception)

    def polling_pod_crawl(self, timeout, ignore_plugin_exception=True):
        raise NotImplementedError()
