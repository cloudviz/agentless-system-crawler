import logging
import socket
from kubernetes import client, config

logger = logging.getLogger('crawlutils')

class KubernetesClient(object):
    '''
    Used for communicating with k8s API server.
    This client generates v1.Pod object and passes it to each clawer plugin.

    This utility class depends on Kubernetes Python Library,
    which is developped in kube-incubator project.

    v1.Pod object has compatibility for Kubernetes Object Model.
    See also Kuberenetes REST API Reference.
    https://kubernetes.io/docs/api-reference/v1/definitions
    '''

    def __init__(self, namespace=None):
        self.namespace = namespace
        self.hostname = socket.gethostname()
        self.ipaddr = socket.gethostbyname(self.hostname)

        # TODO: multiple KUBE_CONFIG support
        # current version refers to k8s authentication config on
        # DEFAULT KUBE CONFIG PATH (~/.kube/config) only.
        # need to set .kube/config before crawling
        config.load_kube_config()
        self.v1client = client.CoreV1Api()

    def list_all_pods(self):
        '''
        list up all living v1.Pod objects managed in this host,
        then yield matched v1.Pod object to crawler plugin
        '''
        # V1PodList
        podList = self.v1client.list_pod_for_all_namespaces()
        for pod in podList.items:
            if pod.status.host_ip == self.ipaddr:
                yield pod
