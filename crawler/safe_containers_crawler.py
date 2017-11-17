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
from containers import poll_containers, get_containers
from utils.crawler_exceptions import ContainerWithoutCgroups

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
        self.frequency = frequency
        #magic numbers
        #self.plugincont_image = 'plugincont_image'
        self.plugincont_image = 'crawler_plugins15'
        self.plugincont_name = 'plugin_cont'
        self.plugincont_username = 'user1'
        self.plugincont_workdir = '/home/user1/features/'
        self.plugincont_seccomp_profile_path = os.getcwd() + '/crawler/utils/plugincont/seccomp-no-ptrace.json'
        self.plugincont_guestcont_mountpoint = '/rootfs_local'
        self.plugincont_host_uid = '166536' #from  docker userns remapping
        self.plugincont_cgroup_netclsid = '43'  #random cgroup net cls id

    
    def destroy_plugincont(self, guestcont):
        client = docker.APIClient(base_url='unix://var/run/docker.sock') 
        plugincont_id = guestcont.plugincont.id
        client.stop(plugincont_id)
        client.remove_container(plugincont_id)
        guestcont.plugincont = None

    def create_plugincont(self, guestcont):
        #TODO: build plugin cont image from Dockerfile first

        #pip install docker=2.0.0          
        #client.containers.run("ruby", "tail -f /dev/null", pid_mode='container:d98cd4f1e518e671bc376ac429146937fbec9df7dbbfbb389e615a90c23ca27a', detach=True)
        # maybe userns_mode='host' 
        guestcont_id = guestcont.long_id
        guestcont_rootfs = utils.dockerutils.get_docker_container_rootfs_path(guestcont_id)
        plugincont = None
        seccomp_attr = json.dumps(json.load(open(self.plugincont_seccomp_profile_path)))
        #secomp_profile_path = os.getcwd() + self.plugincont_seccomp_profile_path
        client = docker.from_env()          
        try:
            plugincont = client.containers.run(
                image=self.plugincont_image, 
                #name=self.plugincont_name,
                user=self.plugincont_username,
                command="/usr/bin/python2.7 /crawler/crawler/crawler_lite.py --frequency="+str(self.frequency),
                #command="tail -f /dev/null",
                pid_mode='container:'+guestcont_id,
                network_mode='container:'+guestcont_id,
                cap_add=["SYS_PTRACE","DAC_READ_SEARCH"],
                #security_opt=['seccomp:'+seccomp_profile_path],
                security_opt=['seccomp:'+seccomp_attr],
                volumes={guestcont_rootfs:{'bind':self.plugincont_guestcont_mountpoint,'mode':'ro'}},
                detach=True)
        except Exception as exc:      
            print exc
            print sys.exc_info()[0]
        guestcont.plugincont = plugincont

    def _add_iptable_rules(self):
        # pip install python-iptables
        retVal = 0
        try:
            rule = iptc.Rule()
            match = iptc.Match(rule, "owner")
            match.uid_owner = self.plugincont_host_uid  
            rule.add_match(match)
            rule.dst = "!localhost"
            rule.protocol = "all"
            rule.target = iptc.Target(rule, "DROP")
            chain = iptc.Chain(iptc.Table(iptc.Table.FILTER), "OUTPUT")
            chain.insert_rule(rule)
                
            rule = iptc.Rule()
            match = iptc.Match(rule, "cgroup")
            match.cgroup =  self.plugincont_cgroup_netclsid 
            rule.add_match(match)
            rule.src = "!localhost"
            rule.target = iptc.Target(rule, "DROP")
            chain = iptc.Chain(iptc.Table(iptc.Table.FILTER), "INPUT")
            chain.insert_rule(rule)
        except:
            print sys.exc_info()[0]
            retVal = -1
        return retVal

    def _get_cgroup_dir(self, devlist=[]):
        for dev in devlist:
            paths = [os.path.join('/cgroup/', dev),
                     os.path.join('/sys/fs/cgroup/', dev)]
            for path in paths:
                if os.path.ismount(path):
                    return path

            # Try getting the mount point from /proc/mounts
            for l in open('/proc/mounts', 'r'):
                _type, mnt, _, _, _, _ = l.split(' ')
                if _type == 'cgroup' and mnt.endswith('cgroup/' + dev):
                    return mnt

        raise ContainerWithoutCgroups('Can not find the cgroup dir')

    def _setup_netcls_cgroup(self, plugincont_id):
        retVal = 0
        try:
            # cgroup_netcls_path = '/sys/fs/cgroup/net_cls/docker/'+plugincont_id
            cgroup_netcls_path = _get_cgroup_dir(['net_cls','net_cls,net_prio'])+'/docker/'+plugincont_id
            tasks_path = cgroup_netcls_path+'/tasks'
            block_path = cgroup_netcls_path+'/block'
            block_classid_path = block_path+'/net_cls.classid'
            block_tasks_path = block_path+'/tasks'
            
            if not os.path.isdir(block_path):
                os.makedirs(block_path)
            
            fd = open(block_classid_path,'w')
            fd.write(self.plugincont_cgroup_netclsid)
            fd.close()
            
            fd = open(tasks_path,'r')
            plugincont_pids = fd.readlines()  #should be just one pid == plugincont_pid
            fd.close()
            
            fd = open(block_tasks_path,'r')
            for pid in plugincont_pids:
                fd.write(pid)
            fd.close()
        except:      
            print sys.exc_info()[0]
            retVal = -1
        return retVal    
        
    def set_plugincont_iptables(self, plugincont_id):
        retVal = 0
        try:
            client = docker.APIClient(base_url='unix://var/run/docker.sock')          
            plugincont_pid = client.inspect_container(plugincont_id)['State']['Pid']     
            #netns_path = '/var/run/netns'
            #if not os.path.isdir(netns_path):
            #    os.makedirs(netns_path)
            retVal = self._setup_netcls_cgroup(plugincont_id, plugincont_pid)
            if retVal == 0:
                retVal = run_as_another_namespace(plugincont_pid,
                                         ['net'],
                                         self._add_iptable_rules)
        except:      
            print sys.exc_info()[0]
            retVal = -1
        return retVal    
    
    def setup_plugincont(self, guestcont):
        self.create_plugincont(guestcont)
        if guestcont.plugincont is not None:
            plugincont_id = guestcont.plugincont.id 
            if self.set_plugincont_iptables(plugincont_id) != 0:
                #TODO: uncomment following
                #self.destroy_plugincont(guestcont)                
                guestcont.plugincont = None

    # Return list of features after reading frame from plugin cont
    def get_plugincont_features(self, guestcont):
        features = []
        if guestcont.plugincont is None:
            self.setup_plugincont(guestcont)
            if guestcont.plugincont is None:
                return features
            
        plugincont_id = guestcont.plugincont.id
        rootfs = utils.dockerutils.get_docker_container_rootfs_path(plugincont_id)
        frame_dir = rootfs+self.plugincont_workdir
        try:
            frame_list = os.listdir(frame_dir)
            frame_list.sort(key=int)
            if frame_list != []:
                earliest_frame_file = frame_dir+frame_list[0]
                fd = open(earliest_frame_file)
                for feature_line in fd.readlines():
                    (type, key, val) = feature_line.strip().split()
                    features.append((key, ast.literal_eval(val), type))
                fd.close()    
                os.remove(earliest_frame_file)
        except:
            print sys.exc_info()[0]
        
        return features
            

    def crawl_container(self, container, ignore_plugin_exception=True):
        frame = ContainerFrame(self.features, container)
        try:
            import pdb
            pdb.set_trace()
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
            #import pdb
            #pdb.set_trace()
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
        containers_list = get_containers(
            user_list=self.user_list,
            host_namespace=self.host_namespace)
        for container in containers_list:
            yield self.crawl_container(container, ignore_plugin_exception)
