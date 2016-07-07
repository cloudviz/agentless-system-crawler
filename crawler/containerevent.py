"""
container event object
"""

class ContainerEvent(object):
        def __init__(self, cId, imgId, event, etime):
                self.cId = cId
                self.imgId = imgId
                self.event = event
                self.eventTime = etime

        def get_containerid(self):
                return self.cId

        def get_imgageid(self):
                return self.imgId

        def get_event(self):
                return self.event
                      
        def get_eventTime(self):
                return eventTime


