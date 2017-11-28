import ast
import os
import sys
import time
import json
import docker
import iptc
import plugins_manager
import utils.dockerutils
from base_crawler import BaseCrawler, BaseFrame
from plugin_containers_manager import PluginContainersManager
from containers import poll_containers, get_containers
from utils.crawler_exceptions import ContainerWithoutCgroups
from utils.namespace import run_as_another_namespace

class ContainerFrame(BaseFrame):

    def __init__(self, feature_types, container):
        BaseFrame.__init__(self, feature_types)
        self.metadata.update(container.get_metadata_dict())
        self.metadata['system_type'] = 'container'


class SafeContainersCrawler(BaseCrawler):

    def __init__(self,
                 features=['os', 'cpu'],
                 environment='cloudsight',
                 user_list='ALL',
                 host_namespace='',
                 plugin_places=['plugins'],
                 frequency=-1,
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
        self.pluginconts_manager = None
        try:
            self.pluginconts_manager = PluginContainersManager(frequency)
        except ValueError as err:
            print(err.args)
   
    # Return list of features after reading frame from plugin cont
    def get_plugincont_features(self, guestcont):
        #import pdb
        #pdb.set_trace()
        features = []
        if self.pluginconts_manager is None:
            return features

        if guestcont.plugincont is None:
            self.pluginconts_manager.setup_plugincont(guestcont)
            if guestcont.plugincont is None:
                return features
        frame_dir = self.pluginconts_manager.get_plugincont_framedir(guestcont)    
        try:
            frame_list = os.listdir(frame_dir)
            frame_list.sort(key=int)
            if frame_list != []:
                earliest_frame_file = frame_dir+frame_list[0]
                fd = open(earliest_frame_file)
                for feature_line in fd.readlines():
                    (type, key, val) = feature_line.strip().split('\t')
                    features.append((ast.literal_eval(key), ast.literal_eval(val), type))
                fd.close()    
                os.remove(earliest_frame_file)
        except Exception as exc:      
            print exc
            print sys.exc_info()[0]
        
        return features
            

    def crawl_container(self, container, ignore_plugin_exception=True):
        frame = ContainerFrame(self.features, container)
        try:
            frame.add_features(self.get_plugincont_features(container))
        except Exception as exc:
            if not ignore_plugin_exception:
                raise exc
        return frame

    def crawl_container_org(self, container, ignore_plugin_exception=True):
        """
        Crawls a specific container and returns a Frame for it.

        :param container: a Container object
        :param ignore_plugin_exception: just ignore exceptions in a plugin
        :return: a Frame object. The returned frame can have 0 features and
        still have metadata. This can occur if there were no plugins, or all
        the plugins raised an exception (and ignore_plugin_exception was True).
        """
        frame = ContainerFrame(self.features, container)

        # collect plugin crawl output for privileged plugins run at host
        for (plugin_obj, plugin_args) in self.plugins:
            try:
                frame.add_features(
                    plugin_obj.crawl(
                        container_id=container.long_id,
                        **plugin_args))
            except Exception as exc:
                if not ignore_plugin_exception:
                    raise exc

        # collect plugin crawl output from inside plugin sidecar container
        try:
            frame.add_features(self.get_plugincont_features(container))
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
        # Not implemented
        time.sleep(timeout)      
        return None

    def crawl(self, ignore_plugin_exception=True):
        """
        Crawls all containers.

        :param ignore_plugin_exception: just ignore exceptions in a plugin
        :return: a list generator of Frame objects
        """
        if self.pluginconts_manager is None:
            return
        containers_list = get_containers(
            user_list=self.user_list,
            host_namespace=self.host_namespace,
            group_by_pid_namespace=False)
        for container in containers_list:
            if not container.name.startswith(self.pluginconts_manager.plugincont_name_prefix):
                yield self.crawl_container(container, ignore_plugin_exception)
