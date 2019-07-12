import logging

from icrawl_plugin import IHostCrawler
from utils.config_utils import crawl_config_files

logger = logging.getLogger('crawlutils')


class ConfigHostCrawler(IHostCrawler):

    def get_feature(self):
        return 'config'

    def crawl(
            self,
            root_dir='/',
            exclude_dirs=[
                '/dev',
                '/proc',
                '/mnt',
                '/tmp',
                '/var/cache',
                '/var/lib',
                '/var/log',
                '/usr',
                '/usr/share/man',
                '/usr/share/doc',
                '/usr/share/mime'],
            known_config_files=[
                '/confuse_proxy_etc/login.defs',
                '/confuse_proxy_etc/passwd',
                '/confuse_proxy_etc/group',
                '/confuse_proxy_etc/hostname',
                '/confuse_proxy_etc/kubernetes/pki/ca.crt',
                '/confuse_proxy_etc/kubernetes/kubelet/kubelet-config.json',
                '/confuse_proxy_etc/systemd/system/kubelet.service.d/10-kubeadm.conf',
                '/confuse_proxy_etc/kubernetes/kubelet.conf',
                '/confuse_proxy_etc/kubernetes/apiserver.conf',
                '/confuse_proxy_etc/kubernetes/controller-manager.conf',
                '/confuse_proxy_etc/confuse_proxy_etcd/confuse_proxy_etcd.conf',
                '/confuse_proxy_etc/sysconfig/flanneld',
                '/confuse_proxy_etc/kubernetes/manifests/etcd.yaml',
                '/var/lib/kubelet/config.yaml',
                '/confuse_proxy_etc/systemd/system/kubelet.service.d/10-kubeadm.conf',
                '/confuse_proxy_etc/kubernetes/proxy.conf',
                '/confuse_proxy_etc/kubernetes/scheduler.conf'],
            discover_config_files=False,
            **kwargs):
        return crawl_config_files(
            root_dir=root_dir,
            exclude_dirs=exclude_dirs,
            known_config_files=known_config_files,
            discover_config_files=discover_config_files)
