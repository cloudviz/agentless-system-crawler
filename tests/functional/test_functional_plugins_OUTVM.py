import unittest
import subprocess
import time

from crawler.plugins.os_vm_crawler import os_vm_crawler
from crawler.plugins.process_vm_crawler import process_vm_crawler
from crawler.plugins.memory_vm_crawler import MemoryVmCrawler
from crawler.plugins.connection_vm_crawler import ConnectionVmCrawler
from crawler.plugins.interface_vm_crawler import InterfaceVmCrawler
from crawler.plugins.metric_vm_crawler import MetricVmCrawler

from crawler.features import (
    ProcessFeature,
    MetricFeature,
    MemoryFeature,
)


# Tests the FeaturesCrawler class
# Throws an AssertionError if any test fails

class VmPluginsFunctionalTests(unittest.TestCase):

    SETUP_ONCE = False
    vm_descs = [['vm2', '4.0.3.x86_64', 'vanilla', 'x86_64'],
                ['vm3', '3.2.0-101-generic_3.2.0-101.x86_64',
                    'ubuntu', 'x86_64'],
                ['vm4', '3.13.0-24-generic_3.13.0-24.x86_64',
                    'ubuntu', 'x86_64']
                ]

    def create_vm_via_bash(self, vmID):
        qemu_out_file = "/tmp/psvmi_qemu_out"
        serial = "file:" + qemu_out_file

        vmlinuz = "psvmi/tests/vmlinuz/vmlinuz-" + vmID[1]
        vm_name = vmID[0]

        disk_file = "psvmi/tests/" + vm_name + "disk.qow2"
        subprocess.call(["cp", "psvmi/tests/disk.qcow2", disk_file])
        disk = "format=raw,file=" + disk_file

        qemu_cmd = subprocess.Popen(
            ("qemu-system-x86_64",
             "-kernel",
             vmlinuz,
             "-append",
             ("init=psvmi_test_init root=/dev/sda console=ttyAMA0 "
              "console=ttyS0"),
             "-name",
             vm_name,
             "-m",
             "512",
             "-smp",
             "1",
             "-drive",
             disk,
             "-display",
             "none",
             "-serial",
             serial))

        vmID.append(str(qemu_cmd.pid))  # vmID[4]=qemu_pid

        # ugly way to fiogure out if a VM has booted, could not pipe output
        # from qemu properly
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

    def setUp(self):
        if VmPluginsFunctionalTests.SETUP_ONCE is False:
            for vm_desc in VmPluginsFunctionalTests.vm_descs:
                self.create_vm_via_bash(vm_desc)
            VmPluginsFunctionalTests.SETUP_ONCE = True
        self.vm_descs = VmPluginsFunctionalTests.vm_descs

    @classmethod
    def teardown_class(cls):
        for _, _, _, _, pid in VmPluginsFunctionalTests.vm_descs:
            subprocess.call(["kill", "-9", pid])

    def _tearDown(self):
        for _, _, _, _, pid in self.vm_descs:
            subprocess.call(["kill", "-9", pid])
            # no need to rm qcow disk files since they get destroyed on
            # container exit

    def test_crawl_outvm_os(self):
        fc = os_vm_crawler()
        for _, kernel, distro, arch, pid in self.vm_descs:
            for item in fc.crawl(vm_desc=(pid, kernel, distro, arch)):
                assert 'Linux' in item

    def test_crawl_outvm_process(self):
        fc = process_vm_crawler()
        for _, kernel, distro, arch, pid in self.vm_descs:
            for item in fc.crawl(vm_desc=(pid, kernel, distro, arch)):
                p = ProcessFeature._make(item[1])
                if p.pid == 0:
                    assert 'swapper' in str(p.pname)
                elif p.pname == 'psvmi_test_init':
                    assert 'devconsole' in str(p.openfiles)
                else:
                    assert p.pid > 0

    def test_crawl_outvm_mem(self):
        fc = MemoryVmCrawler()
        for _, kernel, distro, arch, pid in self.vm_descs:
            for item in fc.crawl(vm_desc=(pid, kernel, distro, arch)):
                meminfo = MemoryFeature._make(item[1])
                assert (meminfo.memory_util_percentage >= 0)

    def test_crawl_outvm_metrics(self):
        fc = MetricVmCrawler()
        for _, kernel, distro, arch, pid in self.vm_descs:
            for item in fc.crawl(vm_desc=(pid, kernel, distro, arch)):
                p = MetricFeature._make(item[1])
                if p.pname == 'psvmi_test_init':
                    assert p.rss > 0
                    assert p.vms > 0
                    assert p.mempct >= 0
                    # stritly speaking > 0 but due to rounding

            # to see if 100% cpu util shows up for psvmi_test_init
            # time.sleep(1)
            # print list(crawler.crawl_metrics())

    def _test_crawl_outvm_modules(self):
        for crawler in self.crawlers:
            output = crawler.crawl_modules()
            assert len(list(output)) > 0

    def test_crawl_outvm_interface(self):
        fc = InterfaceVmCrawler()
        for _, kernel, distro, arch, pid in self.vm_descs:
            output = fc.crawl(vm_desc=(pid, kernel, distro, arch))
            assert any('lo' in item[0] for item in output)

    def test_crawl_outvm_connections(self):
        fc = ConnectionVmCrawler()
        for _, kernel, distro, arch, pid in self.vm_descs:
            output = fc.crawl(vm_desc=(pid, kernel, distro, arch))
            assert len(list(output)) == 0  # There are no connections

    if __name__ == '__main__':
        unittest.main()
