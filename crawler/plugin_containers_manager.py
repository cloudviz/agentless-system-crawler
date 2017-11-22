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
from utils.namespace import run_as_another_namespace

class PluginContainersManager():

    def __init__(self, frequency=-1):
        self.frequency = frequency
        self.pluginconts = dict()
        #self.plugincont_image = 'plugincont_image'
        self.plugincont_image = 'crawler_plugins18'
        self.plugincont_name_prefix = 'plugin_cont'
        self.plugincont_username = 'user1'
        self.plugincont_framedir = '/home/user1/features/'
        self.plugincont_seccomp_profile_path = os.getcwd() + '/crawler/utils/plugincont/seccomp-no-ptrace.json'
        self.plugincont_guestcont_mountpoint = '/rootfs_local'
        self.plugincont_host_uid = '166536' #from  docker userns remapping
        self.plugincont_cgroup_netclsid = '43'  #random cgroup net cls id

    def get_plugincont_framedir(self, guestcont):
        frame_dir = None
        if guestcont is not None and guestcont.plugincont is not None:
            plugincont_id = guestcont.plugincont.id
            rootfs = utils.dockerutils.get_docker_container_rootfs_path(plugincont_id)
            frame_dir = rootfs+self.plugincont_framedir
        return frame_dir    

    def destroy_cont(self, id=None, name=None):
        client = docker.APIClient(base_url='unix://var/run/docker.sock')
        if name is None and id is None:
            return
        if name is not None:
            _id = name
            filter = {'name':name}
        else:
            _id = id
            filter = {'id':id}
        if client.containers(all=True,filters=filter) != []:
            client.stop(_id)
            client.remove_container(_id)

    def create_plugincont(self, guestcont):
        #TODO: build plugin cont image from Dockerfile first

        #pip install docker=2.0.0          
        #client.containers.run("ruby", "tail -f /dev/null", pid_mode='container:d98cd4f1e518e671bc376ac429146937fbec9df7dbbfbb389e615a90c23ca27a', detach=True)
        # maybe userns_mode='host' 
        guestcont_id = guestcont.long_id
        guestcont_rootfs = utils.dockerutils.get_docker_container_rootfs_path(guestcont_id)
        plugincont = None
        plugincont_name = self.plugincont_name_prefix+'_'+guestcont_id
        seccomp_attr = json.dumps(json.load(open(self.plugincont_seccomp_profile_path)))
        #secomp_profile_path = os.getcwd() + self.plugincont_seccomp_profile_path
        client = docker.from_env()          
        try:
            self.destroy_cont(name=plugincont_name)
            plugincont = client.containers.run(
                image=self.plugincont_image, 
                name=plugincont_name,
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
            time.sleep(5)    
        except Exception as exc:      
            print exc
            print sys.exc_info()[0]
        
        self.pluginconts[str(guestcont_id)] = plugincont
        guestcont.plugincont = plugincont

    def _add_iptable_rules(self):
        # pip install python-iptables
        retVal = 0
        try:
            rule = iptc.Rule()
            match = iptc.Match(rule, "owner")
            match.uid_owner = self.plugincont_host_uid  
            rule.add_match(match)
            rule.dst = "!127.0.0.1"
            rule.target = iptc.Target(rule, "DROP")
            chain = iptc.Chain(iptc.Table(iptc.Table.FILTER), "OUTPUT")
            chain.insert_rule(rule)
                
            rule = iptc.Rule()
            match = iptc.Match(rule, "cgroup")
            match.cgroup =  self.plugincont_cgroup_netclsid 
            rule.add_match(match)
            rule.src = "!127.0.0.1"
            rule.target = iptc.Target(rule, "DROP")
            chain = iptc.Chain(iptc.Table(iptc.Table.FILTER), "INPUT")
            chain.insert_rule(rule)
        except Exception as exc:      
            print exc
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
            cgroup_netcls_path = self._get_cgroup_dir(['net_cls','net_cls,net_prio'])+'/docker/'+plugincont_id
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
            
            fd = open(block_tasks_path,'w')
            for pid in plugincont_pids:
                fd.write(pid)
            fd.close()
        except Exception as exc:      
            print exc
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
            retVal = self._setup_netcls_cgroup(plugincont_id)
            if retVal == 0:
                retVal = run_as_another_namespace(str(plugincont_pid),
                                         ['net'],
                                         self._add_iptable_rules)
        except Exception as exc:      
            print exc
            print sys.exc_info()[0]
            retVal = -1
        return retVal    
    
    def destroy_plugincont(self, guestcont):
        guestcont_id = str(guestcont.long_id)
        plugincont_id = guestcont.plugincont.id 
        self.destroy_cont(id=plugincont_id)                
        guestcont.plugincont = None
        self.pluginconts.pop(str(guestcont_id))

    def setup_plugincont(self, guestcont):
        guestcont_id = str(guestcont.long_id)
        if guestcont_id in self.pluginconts.keys():
            guestcont.plugincont = self.pluginconts[guestcont_id]
            return

        self.create_plugincont(guestcont)
        if guestcont.plugincont is not None:
            plugincont_id = guestcont.plugincont.id 
            if self.set_plugincont_iptables(plugincont_id) != 0:
                self.destroy_plugincont(guestcont)

