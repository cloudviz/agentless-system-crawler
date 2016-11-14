import unittest
import tempfile
import os
import subprocess
import time

# Tests for crawlers in kraken crawlers configuration.

import crawler.crawlutils
import crawler.config_parser

# Tests conducted with a single container running.


class CrawlutilsVMTest(unittest.TestCase):

    SETUP_ONCE = False

    vmIDs = [['vm2', '4.0.3.x86_64', 'vanilla', 'x86_64'],
             ['vm3', '3.2.0-101-generic_3.2.0-101.x86_64', 'ubuntu', 'x86_64'],
             ['vm4', '3.13.0-24-generic_3.13.0-24.x86_64', 'ubuntu', 'x86_64']
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

    def create_vms(self):
        for vmID in CrawlutilsVMTest.vmIDs:
            self.create_vm_via_bash(vmID)

    @classmethod
    def teardown_class(cls):
        for vmID in CrawlutilsVMTest.vmIDs:
            subprocess.call(["kill", "-9", vmID[4]])

    def setUp(self):
        self.tempd = tempfile.mkdtemp(prefix='crawlertest.')
        if CrawlutilsVMTest.SETUP_ONCE is False:
            self.create_vms()
            CrawlutilsVMTest.SETUP_ONCE = True

    def testCrawlVM1(self):
        os.makedirs(self.tempd + '/out')

        options = {'vm_list': [
            'vm2,4.0.3.x86_64,vanilla,x86_64',
            'vm3,3.2.0-101-generic_3.2.0-101.x86_64,ubuntu,x86_64',
            'vm4,3.13.0-24-generic_3.13.0-24.x86_64,ubuntu,x86_64'],
            'memory': {},
            'interface': {}}

        features = ['memory', 'interface']
        crawler.config_parser.apply_user_args(
            options=options, params={'features': features})
        crawler.plugins_manager.reload_vm_crawl_plugins(
            features=features
        )

        crawler.crawlutils.snapshot_vms(urls=[
            'file://' + self.tempd + '/out/crawler'],
            features=features,
            format='graphite',
            options=options)

        subprocess.call(['/bin/chmod', '-R', '777', self.tempd])

        files = os.listdir(self.tempd + '/out')
        assert len(files) == len(CrawlutilsVMTest.vmIDs)

        f = open(self.tempd + '/out/' + files[0], 'r')
        output = f.read()
        print output  # only printed if the test fails
        assert 'memory.memory-used' in output
        assert 'interface-lo.if_octets.tx' in output
        f.close()

    def testCrawlVM2(self):
        env = os.environ.copy()
        mypath = os.path.dirname(os.path.realpath(__file__))
        os.makedirs(self.tempd + '/out')

        process = subprocess.Popen(
            [
                '/usr/bin/python', mypath + '/../../crawler/crawler.py',
                '--url', 'file://' + self.tempd + '/out/crawler',
                '--features', 'os,memory,interface,process',
                '--crawlVMs', 'vm2,4.0.3.x86_64,vanilla,x86_64',
                'vm3,3.2.0-101-generic_3.2.0-101.x86_64,ubuntu,x86_64',
                'vm4,3.13.0-24-generic_3.13.0-24.x86_64,ubuntu,x86_64',
                '--crawlmode', 'OUTVM',
                '--numprocesses', '1'
            ],
            env=env)
        stdout, stderr = process.communicate()
        assert process.returncode == 0

        print stderr
        print stdout

        subprocess.call(['/bin/chmod', '-R', '777', self.tempd])

        files = os.listdir(self.tempd + '/out')
        assert len(files) == len(CrawlutilsVMTest.vmIDs)

        f = open(self.tempd + '/out/' + files[0], 'r')
        output = f.read()
        print output  # only printed if the test fails
        assert 'psvmi_test_init' in output
        assert 'Linux' in output
        assert 'memory_used' in output
        assert 'interface-lo' in output
        f.close()

    if __name__ == '__main__':
        unittest.main()
