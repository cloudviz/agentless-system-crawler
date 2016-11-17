import docker


class Inspector(object):
    '''
    Interface class.
    '''

    def __init__(self, container_id):
        self.client = docker.Client(
            base_url='unix://var/run/docker.sock', version='auto')
        self.inspects = self.client.inspect_container(container_id)
        self.containers = self.client.containers()

    def is_app_container(self, app=''):
        '''
        Check whether this container is expected application container or not.

        Use inspect information. If not present app name in image name,
        this method returns false.

        :param app: application name
        :return:
        '''

        if self.inspects['Config']['Image'].find(app) == -1:
            return False
        else:
            return True

    def get_ip(self):
        pass

    def get_ports(self):
        ports = []
        for item in self.inspects['Config']['ExposedPorts'].keys():
            ports.append(item.split('/')[0])
        return ports


class PodInspector(Inspector):
    '''
    Utility class for searching ip and ports for app container managed by kubernetes.
    '''

    def get_ip(self):
        pod_name = self.inspects['Config']['Labels']['io.kubernetes.pod.name']
        pod_ip = ""

        # search pause container to know actual pod IP address
        for c in self.containers:
            if c['Image'].find('pause') != -1 and pod_name == c['Labels']['io.kubernetes.pod.name']:
                pod_ip = c['NetworkSettings'][
                    'Networks']['bridge']['IPAddress']
                break
        return pod_ip


class ContainerInspector(Inspector):
    '''
    Utility class for searching ip and ports for app container on Docker.
    '''

    def get_ip(self):
        ip = self.inspects['NetworkSettings'][
            'Networks']['bridge']['IPAddress']
        return ip
