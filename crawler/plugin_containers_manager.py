import os
import sys
import time
import json
import docker
import iptc
import shutil
import ctypes
import utils.dockerutils
from utils.crawler_exceptions import ContainerWithoutCgroups
from utils.namespace import run_as_another_namespace


class PluginContainersManager():

    def __init__(self, frequency=-1):
        self.frequency = frequency
        self.pluginconts = dict()
        self.plugincont_image = 'plugincont_image'
        self.plugincont_name_prefix = 'plugin_cont'
        self.plugincont_username = 'plugincont_user'
        self.plugincont_framedir = '/home/' + \
            self.plugincont_username + '/features/'
        self.plugincont_py_path = '/usr/bin/python2.7'
        self.plugincont_seccomp_profile_path = os.getcwd(
        ) + '/crawler/utils/plugincont/seccomp-no-ptrace.json'
        self.plugincont_image_path = os.getcwd() + \
            '/crawler/utils/plugincont/plugincont_img'
        self.plugincont_guestcont_mountpoint = '/rootfs_local'
        self.docker_client = docker.DockerClient(
            base_url='unix://var/run/docker.sock', version='auto')
        self.docker_APIclient = docker.APIClient(
            base_url='unix://var/run/docker.sock', version='auto')
        if self.set_plugincont_uid() == -1:
            raise ValueError('Failed to verify docker userns-remap settings')
        if self.set_plugincont_cgroup_netclsid() == -1:
            raise ValueError('Failed to set cgroup netclsid')
        if self.build_plugincont_img() != 0:
            raise ValueError('Failed to build image')

    def is_int(self, s):
        try:
            int(s)
            return True
        except ValueError:
            return False

    def _get_next_uid(self):
        # TODO: check uid is within [UID_MIN,UID_MAX] in /etc/login.defs
        # alternate approach: useradd nextid; id -u nextid; userdel nextid
        # assumption the unused uid on host is also an unused uid in container
        # exact ranges maybe found in /etc/subuid
        uid = 1010
        uids_in_use = []
        try:
            fd = open('/etc/passwd', 'r')
            for users in fd.readlines():
                uids_in_use.append(users.split(':')[2])
            fd.close()
            while str(uid) in uids_in_use:
                uid = uid + 1
        except Exception as exc:
            print sys.exc_info()[0], exc, sys.exc_info()[-1].tb_lineno
            uid = -1
        return uid

    def set_plugincont_dockerfile_uid(self, uid):
        retVal = 0
        uid = str(uid)
        user = self.plugincont_username
        try:
            shutil.copyfile(
                self.plugincont_image_path + '/Dockerfile.template',
                self.plugincont_image_path + '/Dockerfile')
            fd = open(self.plugincont_image_path + '/Dockerfile', 'a')
            fd.write('RUN groupadd -r ' + user + ' -g ' + uid + '\n')
            fd.write('RUN useradd -u ' + uid +
                     ' -m ' + user + ' -g ' + user + '\n')
            fd.write('RUN usermod -a -G ' + user + ' ' + user + '\n')
            fd.write('RUN chsh -s /bin/bash ' + user + '\n')
            fd.close()
        except Exception as exc:
            print sys.exc_info()[0], exc, sys.exc_info()[-1].tb_lineno
            retVal = -1
        return retVal

    def set_plugincont_uid(self):
        self.plugincont_host_uid = -1
        try:
            uid = self._get_next_uid()
            if uid <= 0:
                return -1
            if self.set_plugincont_dockerfile_uid(uid) != 0:
                return -1
            self.plugincont_host_uid = uid
            # /var/lib/docker/165536.16553 from docker userns remapping
            docker_root_dir = utils.dockerutils._get_docker_root_dir()
            leaf_dir = docker_root_dir.split('/')[-1]   # 165536.165536
            possible_sub_uid = leaf_dir.split('.')[0]   # 165536
            if self.is_int(possible_sub_uid) is True:
                self.plugincont_host_uid = int(possible_sub_uid) + uid
        except Exception as exc:
            print sys.exc_info()[0], exc, sys.exc_info()[-1].tb_lineno
            self.plugincont_host_uid = -1
        return self.plugincont_host_uid

    def set_plugincont_cgroup_netclsid(self):
        # self.plugincont_cgroup_netclsid = '43'  #random cgroup net cls id
        res_clsid = -1
        try:
            cgroup_netcls_path = self._get_cgroup_dir(
                ['net_cls', 'net_cls,net_prio'])
            for root, dirs, files in os.walk(cgroup_netcls_path):
                for file in files:
                    if file.endswith('net_cls.classid'):
                        fd = open(root + '/' + file, 'r')
                        clsid = int(fd.readline(), 16)
                        if res_clsid <= clsid:
                            res_clsid = clsid + 1
                        fd.close()
            res_clsid = res_clsid + 2
        except Exception as exc:
            print sys.exc_info()[0], exc, sys.exc_info()[-1].tb_lineno
            res_clsid = -1
        self.plugincont_cgroup_netclsid = res_clsid

    def destroy_cont(self, id=None, name=None):
        client = self.docker_APIclient
        if name is None and id is None:
            return
        if name is not None:
            _id = name
            filter = {'name': name}
        else:
            _id = id
            filter = {'id': id}
        if client.containers(all=True, filters=filter) != []:
            client.stop(_id)
            client.remove_container(_id)

    def set_plugincont_py_cap(self, plugincont_id):
        retVal = 0
        verify = False
        try:
            rootfs = utils.dockerutils.get_docker_container_rootfs_path(
                plugincont_id)
            py_path = rootfs + self.plugincont_py_path
            libcap = ctypes.cdll.LoadLibrary("libcap.so")
            caps = libcap.cap_from_text(
                'cap_dac_read_search,cap_sys_chroot,cap_sys_ptrace+ep')
            retVal = libcap.cap_set_file(py_path, caps)
            if verify is True:
                libcap.cap_to_text.restype = ctypes.c_char_p
                caps_set = libcap.cap_get_file(py_path, caps)
                caps_set_str = libcap.cap_to_text(caps_set, None)
                assert 'cap_dac_read_search' in caps_set_str
                assert 'cap_sys_chroot' in caps_set_str
                assert 'cap_sys_ptrace' in caps_set_str
        except Exception as exc:
            print sys.exc_info()[0], exc, sys.exc_info()[-1].tb_lineno
            retVal = -1
        return retVal

    def build_plugincont_img(self):
        retVal = 0
        build_status = list(self.docker_APIclient.build(
            path=self.plugincont_image_path, tag=self.plugincont_image))
        assert 'Successfully built' in build_status[-1]
        try:
            plugincont = self.docker_client.containers.run(
                image=self.plugincont_image,
                command="tail -f /dev/null",
                detach=True)
            time.sleep(5)
            retVal = self.set_plugincont_py_cap(plugincont.id)
            if retVal == 0:
                self.docker_APIclient.commit(
                    plugincont.id, repository=self.plugincont_image)
            self.destroy_cont(id=plugincont.id)
        except Exception as exc:
            print sys.exc_info()[0], exc, sys.exc_info()[-1].tb_lineno
            retVal = -1
        return retVal

    def get_plugincont_framedir(self, guestcont):
        frame_dir = None
        if guestcont is not None and guestcont.plugincont is not None:
            plugincont_id = guestcont.plugincont.id
            rootfs = utils.dockerutils.get_docker_container_rootfs_path(
                plugincont_id)
            frame_dir = rootfs + self.plugincont_framedir
        return frame_dir

    def create_plugincont(self, guestcont):
        guestcont_id = guestcont.long_id
        guestcont_rootfs = utils.dockerutils.get_docker_container_rootfs_path(
            guestcont_id)
        plugincont = None
        plugincont_name = self.plugincont_name_prefix + '_' + guestcont_id
        seccomp_attr = json.dumps(
            json.load(open(self.plugincont_seccomp_profile_path)))
        client = self.docker_client
        try:
            self.destroy_cont(name=plugincont_name)
            plugincont = client.containers.run(
                image=self.plugincont_image,
                name=plugincont_name,
                user=self.plugincont_username,
                command="/usr/bin/python2.7 /crawler/crawler_lite.py "
                        "--frequency=" + str(self.frequency),
                pid_mode='container:' + guestcont_id,
                network_mode='container:' + guestcont_id,
                cap_add=["SYS_PTRACE", "DAC_READ_SEARCH"],
                security_opt=['seccomp:' + seccomp_attr],
                volumes={
                    guestcont_rootfs: {
                        'bind': self.plugincont_guestcont_mountpoint,
                        'mode': 'ro'}},
                detach=True)
            time.sleep(5)
        except Exception as exc:
            print sys.exc_info()[0], exc, sys.exc_info()[-1].tb_lineno

        self.pluginconts[str(guestcont_id)] = plugincont
        guestcont.plugincont = plugincont

    def _add_iptable_rules(self):
        retVal = 0
        try:
            rule = iptc.Rule()
            match = iptc.Match(rule, "owner")
            match.uid_owner = str(self.plugincont_host_uid)
            rule.add_match(match)
            rule.dst = "!127.0.0.1"
            rule.target = iptc.Target(rule, "DROP")
            chain = iptc.Chain(iptc.Table(iptc.Table.FILTER), "OUTPUT")
            chain.insert_rule(rule)

            rule = iptc.Rule()
            match = iptc.Match(rule, "cgroup")
            match.cgroup = str(self.plugincont_cgroup_netclsid)
            rule.add_match(match)
            rule.src = "!127.0.0.1"
            rule.target = iptc.Target(rule, "DROP")
            chain = iptc.Chain(iptc.Table(iptc.Table.FILTER), "INPUT")
            chain.insert_rule(rule)
        except Exception as exc:
            print sys.exc_info()[0], exc, sys.exc_info()[-1].tb_lineno
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
            # cgroup_netcls_path =
            # '/sys/fs/cgroup/net_cls/docker/'+plugincont_id
            cgroup_netcls_path = self._get_cgroup_dir(
                ['net_cls', 'net_cls,net_prio']) + '/docker/' + plugincont_id
            tasks_path = cgroup_netcls_path + '/tasks'
            block_path = cgroup_netcls_path + '/block'
            block_classid_path = block_path + '/net_cls.classid'
            block_tasks_path = block_path + '/tasks'

            if not os.path.isdir(block_path):
                os.makedirs(block_path)

            fd = open(block_classid_path, 'w')
            fd.write(str(self.plugincont_cgroup_netclsid))
            fd.close()

            fd = open(tasks_path, 'r')
            plugincont_pids = fd.readlines()
            # should be just one pid == plugincont_pid
            fd.close()

            fd = open(block_tasks_path, 'w')
            for pid in plugincont_pids:
                fd.write(pid)
            fd.close()
        except Exception as exc:
            print sys.exc_info()[0], exc, sys.exc_info()[-1].tb_lineno
            retVal = -1
        return retVal

    def set_plugincont_iptables(self, plugincont_id):
        retVal = 0
        try:
            client = self.docker_APIclient
            plugincont_pid = client.inspect_container(
                plugincont_id)['State']['Pid']
            retVal = self._setup_netcls_cgroup(plugincont_id)
            if retVal == 0:
                retVal = run_as_another_namespace(str(plugincont_pid),
                                                  ['net'],
                                                  self._add_iptable_rules)
        except Exception as exc:
            print sys.exc_info()[0], exc, sys.exc_info()[-1].tb_lineno
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
        if guestcont.plugincont is None:
            return

        plugincont_id = guestcont.plugincont.id
        if self.set_plugincont_iptables(plugincont_id) != 0:
            self.destroy_plugincont(guestcont)
            return
