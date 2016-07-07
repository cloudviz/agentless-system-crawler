import sys
from containerevent import ContainerEvent
import docker

class DockerMonitor(object):
    def __init__(self, eventQ):
        self.eventQ = eventQ
        self.client = docker.Client(base_url='unix://var/run/docker.sock')

    def __container_start_handler(self, event):
        containerid = event['id']
        imageid = event['from']
        epochtime = event['time']
        cEvent = ContainerEvent(containerid, imageid, event['Action'], epochtime)
        self.eventQ.put(cEvent)

     def __container_delete_handler(self, event):
         containerid = event['id']
         imageid = event['from']
         epochtime = event['time']
         cEvent = ContainerEvent(containerid, imageid, event['Action'], epochtime)
         self.eventQ.put(cEvent)

     def startMonitor(self):
         events = self.client.events(decode=True)
         for event in events:
             if event['Action'] == 'start':
                 self.__container_start_handler(event)
             if event['Action'] == 'die':
                 self.__container_delete_handler(event)		

