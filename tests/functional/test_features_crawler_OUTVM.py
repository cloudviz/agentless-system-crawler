import unittest
import docker
import requests.exceptions
import tempfile
import os
import shutil
import subprocess
import time
import re

from crawler.emitter import Emitter
from crawler.features_crawler import FeaturesCrawler

from crawler.dockercontainer import DockerContainer
from crawler.dockerutils import exec_dockerinspect

from crawler.features import (OSFeature, FileFeature, ConfigFeature, DiskFeature,
                      ProcessFeature, MetricFeature, ConnectionFeature,
                      PackageFeature, MemoryFeature, CpuFeature,
                      InterfaceFeature, LoadFeature, DockerPSFeature,
                      DockerHistoryFeature, ModuleFeature, CpuHwFeature)


# Tests the FeaturesCrawler class
# Throws an AssertionError if any test fails

class FeaturesCrawlerTests(unittest.TestCase):
   
    USE_RUNNING_VM = False
    #vmIDs = [['vm2','3.2.0-101-generic_3.2.0-101.x86_64','ubuntu','x86_64']]
    
    SETUP_ONCE = False

    crawlers = [] 
    
    #vmIDs = [['vm2', '4.0.3.x86_64', 'vanilla', 'x86_64']]
    vmIDs = [['vm2', '4.0.3.x86_64', 'vanilla', 'x86_64'],\
            ['vm3', '3.2.0-101-generic_3.2.0-101.x86_64', 'ubuntu', 'x86_64'],\
            ['vm4', '3.13.0-24-generic_3.13.0-24.x86_64', 'ubuntu', 'x86_64']\
            ]
    
    def get_qemu_pid(self, vm_name):
        ps = subprocess.Popen(('ps', 'ax'), stdout=subprocess.PIPE)
        output = ps.communicate()[0]
        for line in output.split('\n'):
             if 'qemu' in line:
                     matchObj = re.match(r'(\s)*([0-9]+) .* -name (.*?) .*', line)
                     if vm_name == matchObj.group(3): #contains 'vm1'
                       pid =  matchObj.group(2)
                       return pid

    def initialize_crawlers(self):
        for _vmID in  FeaturesCrawlerTests.vmIDs:
            #follwoing regex match based pid find works, but no need for complexity!
            #also not grepping for vm name helps when --pid=host is being used to run docker
            #_qemu_pid = self.get_qemu_pid(_vmID[0])
            _vm=(_vmID[4], _vmID[1], _vmID[2], _vmID[3])  #vmID[4]=qemu_pid
            FeaturesCrawlerTests.crawlers.append(FeaturesCrawler(crawl_mode='OUTVM', vm=_vm))

    def create_vm_via_bash(self, vmID):
        qemu_out_file = "/tmp/psvmi_qemu_out"
        serial = "file:" + qemu_out_file

        vmlinuz="psvmi/tests/vmlinuz/vmlinuz-" + vmID[1]
        vm_name = vmID[0]
        
        disk_file = "psvmi/tests/" + vm_name + "disk.qow2"
        subprocess.call(["cp", "psvmi/tests/disk.qcow2", disk_file]) 
        disk = "format=raw,file=" + disk_file

        qemu_cmd = subprocess.Popen(("qemu-system-x86_64",\
                            "-kernel", vmlinuz,\
                            "-append", "init=psvmi_test_init root=/dev/sda console=ttyAMA0 console=ttyS0",\
                            "-name", vm_name,\
                            "-m","512",\
                            "-smp","1",\
                            "-drive", disk,\
                            "-display", "none",\
                            "-serial", serial))

        vmID.append(str(qemu_cmd.pid))  #vmID[4]=qemu_pid

        #ugly way to fiogure out if a VM has booted, could not pipe output from qemu properly
        vm_ready = False
        
        while True:
            time.sleep(4)

            fr = open(qemu_out_file, "r")
            for line in fr.readlines():
                if "Mounted root" in line:
                    time.sleep(3)
                    vm_ready = True
                    break
            fr.close()

            if vm_ready is True:
                break


    def create_vms(self):
        for vmID in  FeaturesCrawlerTests.vmIDs:
            if  FeaturesCrawlerTests.USE_RUNNING_VM is True:
                qemu_pid = self.get_qemu_pid(vmID[0])
                vmID.append(str(qemu_pid))  #vmID[4]=qemu_pid
            else:
                self.create_vm_via_bash(vmID)
               
    def setUp(self):
        if FeaturesCrawlerTests.SETUP_ONCE is False:
            self.create_vms()
            self.initialize_crawlers()
            #self.print_crawler_output()
            FeaturesCrawlerTests.SETUP_ONCE = True
    
    
    @classmethod
    def teardown_class(cls):
        if FeaturesCrawlerTests.USE_RUNNING_VM is True:
            pass
        else: 
            for vmID in FeaturesCrawlerTests.vmIDs:        
                subprocess.call(["kill","-9",vmID[4]])
                #no need to rm qcow disk files since they get destroyed on container exit
    
    
    def print_crawler_output(self):
        for crawler in self.crawlers:
            print list(crawler.crawl_os())
            print list(crawler.crawl_cpuHw())
            print list(crawler.crawl_processes())
            print list(crawler.crawl_memory())
            print list(crawler.crawl_metrics())
            print list(crawler.crawl_modules())
            print list(crawler.crawl_interface())
            print list(crawler.crawl_load())
            print list(crawler.crawl_connections())
    
    def myassert(self, expr):
        assert expr

    def test_features_crawler_crawl_outvm_os(self):
        for crawler in self.crawlers:
            output = crawler.crawl_os()
            assert len(list(output)) > 0

            for item in crawler.crawl_os():
                assert 'Linux' in item



    def test_features_crawler_crawl_outvm_cpuHw(self):
        for crawler in self.crawlers:
            output = crawler.crawl_cpuHw()
            assert len(list(output)) > 0
            
            for item in crawler.crawl_cpuHw():
                assert 'QEMU' in str(item)

    
    def test_features_crawler_crawl_outvm_process(self):
        for crawler in self.crawlers:
            output = crawler.crawl_processes()
            assert len(list(output))>0
            
            #assert any('bash' in ProcessFeature._make(item[1]).pname for item in crawler.crawl_processes())
            
            if FeaturesCrawlerTests.USE_RUNNING_VM is False:
                    assert any('psvmi_test_init' in ProcessFeature._make(item[1]).pname for item in crawler.crawl_processes())
   
            for item in crawler.crawl_processes():
                p =  ProcessFeature._make(item[1])
                if p.pid == 0:
                    assert 'swapper' in str(p.pname)

                elif p.pname == 'psvmi_test_init':
                    assert 'devconsole' in str(p.openfiles)

                else:
                    assert p.pid > 0



    def test_features_crawler_crawl_outvm_mem(self):
        for crawler in self.crawlers:
            output = crawler.crawl_memory()
            assert len(list(output))>0

            for item in crawler.crawl_memory():
                meminfo = MemoryFeature._make(item[1])
                assert (meminfo.memory_util_percentage >= 0) 


    def test_features_crawler_crawl_outvm_metrics(self):
        for crawler in self.crawlers:
            output = crawler.crawl_metrics()
            assert len(list(output))>0
            
            for item in crawler.crawl_metrics():
                p = MetricFeature._make(item[1])
                if p.pname == 'psvmi_test_init':
                    assert p.rss > 0
                    assert p.vms > 0
                    assert p.mempct >= 0 #stritly speaking > 0 but due to rounding in features_crawler.py
           
            #to see if 100% cpu util shows up for psvmi_test_init
            #time.sleep(1)
            #print list(crawler.crawl_metrics())
   
 
    def test_features_crawler_crawl_outvm_modules(self):
        for crawler in self.crawlers:
            output = crawler.crawl_modules()
            assert len(list(output))>0

    def test_features_crawler_crawl_outvm_interface(self):
        for crawler in self.crawlers:
            assert any('lo' in item[0] for item in crawler.crawl_interface())

    def test_features_crawler_crawl_outvm_connections(self):
        for crawler in self.crawlers:
            if self.USE_RUNNING_VM is True:
                output = crawler.crawl_connections()
                assert len(list(output)) > 0
          

    if __name__ == '__main__':
        unittest.main()
