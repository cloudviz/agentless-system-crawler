import psutil


def get_virtual_machines(user_list=[], host_namespace=''):
    """
    Returns the list of Virtual Machines running in the system.

    XXX: Only QEMU VMs are supported at the moment, this includes
    kvm and non-kvm VMs.

    :param user_list: a list of VM descriptor strings 'name,kernel,distro,arch'
    :return: A list of VirtualMachine objects
    """
    if user_list is []:
        raise NotImplementedError(
            'Discovery of virtual machines is not supported')

    vms = []
    for vm_desc in user_list:
        try:
            name, kernel, distro, arch = vm_desc.split(',')
            vms.append(QemuVirtualMachine(name, kernel, distro, arch,
                                          host_namespace=host_namespace))
        except (ValueError, KeyError):
            continue
    return vms


class VirtualMachine():

    def __init__(self, name, kernel, distro, arch, host_namespace=''):
        self.name = name
        self.namespace = host_namespace + '/' + name
        self.kernel = kernel
        self.distro = distro
        self.arch = arch
        self.pid = 0

    def get_vm_desc(self):
        """
        Returns a list of strings, which all identify a VM

        XXX: make this a dictionary

        :return: a VM descriptor to be passed to the VM crawl plugins and used
        to identify the VM.
        """
        return str(self.pid), self.kernel, self.distro, self.arch

    def get_metadata_dict(self):
        return {'namespace': self.namespace, 'name': self.name}


class QemuVirtualMachine(VirtualMachine):

    def __init__(self, name, kernel, distro, arch, host_namespace='',
                 pid=None):
        VirtualMachine.__init__(self, name, kernel, distro, arch,
                                host_namespace=host_namespace)

        if pid is None:
            # Find the pid of the QEMU process running virtual machine `name`
            self.pid = None
            for proc in psutil.process_iter():
                if 'qemu' in proc.name():
                    line = proc.cmdline()
                    if name == line[line.index('-name') + 1]:
                        self.pid = proc.pid

            if self.pid is None:
                raise ValueError('no VM with vm_name: %s' % name)
        else:
            self.pid = pid
