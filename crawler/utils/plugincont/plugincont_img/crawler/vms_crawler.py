import plugins_manager
from base_crawler import BaseCrawler, BaseFrame
from virtual_machine import get_virtual_machines


class VirtualMachineFrame(BaseFrame):

    def __init__(self, feature_types, vm):
        BaseFrame.__init__(self, feature_types)
        self.metadata.update(vm.get_metadata_dict())
        self.metadata['system_type'] = 'vm'


class VirtualMachinesCrawler(BaseCrawler):

    def __init__(self,
                 features=['os', 'cpu'],
                 user_list=[],
                 host_namespace='',
                 plugin_places=['plugins'],
                 options={}):

        BaseCrawler.__init__(
            self,
            features=features,
            plugin_places=plugin_places,
            options=options)
        self.vms_list = []
        plugins_manager.reload_vm_crawl_plugins(
            features, plugin_places, options)
        self.plugins = plugins_manager.get_vm_crawl_plugins(features)
        self.host_namespace = host_namespace
        self.user_list = user_list

    def update_vms_list(self):
        """
        Updates the self.vms_list.

        :return: None
        """
        self.vms_list = get_virtual_machines(
            user_list=self.user_list,
            host_namespace=self.host_namespace)

    def crawl_vm(self, vm, ignore_plugin_exception=True):
        """
        Crawls a specific vm and returns a Frame for it.

        :param vm: a VirtualMachine object
        :param ignore_plugin_exception: just ignore exceptions on a plugin
        :return: a Frame object. The returned frame can have 0 features and
        still have metadata. This can occur if there were no plugins, or all
        the plugins raised an exception (and ignore_plugin_exception was True).
        """
        frame = VirtualMachineFrame(self.features, vm)
        for (plugin_obj, plugin_args) in self.plugins:
            try:
                frame.add_features(plugin_obj.crawl(vm_desc=vm.get_vm_desc(),
                                                    **plugin_args))
            except Exception as exc:
                if not ignore_plugin_exception:
                    raise exc
        return frame

    def crawl_vms(self, ignore_plugin_exception=True):
        """
        Crawl all vms stored in self.vms_list

        :param ignore_plugin_exception: just ignore exceptions in a plugin
        :return: a list generator of Frame objects
        """
        for vm in self.vms_list:
            yield self.crawl_vm(vm, ignore_plugin_exception)

    def crawl(self, ignore_plugin_exception=True):
        """
        Crawl all vms running in the system.

        :param ignore_plugin_exception: just ignore exceptions in a plugin
        :return: a list generator of Frame objects
        """
        self.update_vms_list()
        return self.crawl_vms(ignore_plugin_exception)
