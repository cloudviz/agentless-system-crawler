"""
Docker container event object
"""


class DockerContainerEvent(object):
    def __init__(self, contId, imgId, event, etime):
        self.contId = contId
        self.imgId = imgId
        self.event = event
        self.eventTime = etime

    def get_containerid(self):
        return self.contId

    def get_imgageid(self):
        return self.imgId

    def get_event(self):
        return self.event

    def get_eventTime(self):
        return self.eventTime
