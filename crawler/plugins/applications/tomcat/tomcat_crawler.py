import urllib2
from plugins.applications.tomcat import feature
from xml.etree import ElementTree
from utils.crawler_exceptions import CrawlError


def retrieve_status_page(hostname, port, user, password):
    statusPage = "http://%s:%s/manager/status?XML=true" % (hostname, port)

    password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
    password_mgr.add_password(None, statusPage, user, password)
    handler = urllib2.HTTPBasicAuthHandler(password_mgr)
    opener = urllib2.build_opener(handler)
    urllib2.install_opener(opener)

    req = urllib2.Request(statusPage)
    try:
        response = urllib2.urlopen(req)
        return response.read()
    except Exception:
        raise CrawlError("can't access to http://%s:%s",
                         hostname, port)


def retrieve_metrics(host='localhost', port=8080,
                     user='tomcat', password='password',
                     feature_type='application'):

    status = retrieve_status_page(host, port, user, password)
    tree = ElementTree.XML(status)
    memoryNode = tree.find('jvm/memory')
    jvm_attributes = feature.TomcatJVMFeature(
        memoryNode.get("free"),
        memoryNode.get("total"),
        memoryNode.get("max")
    )

    yield('tomcat_jvm', jvm_attributes, feature_type)

    for node in tree.iter('memorypool'):
        memory_pool_attributes = feature.TomcatMemoryFeature(
            node.get("name"),
            node.get("type"),
            node.get("usageInit"),
            node.get("usageCommitted"),
            node.get("usageMax"),
            node.get("usageUsed")
        )
        yield('tomcat_memory', memory_pool_attributes, feature_type)

    ConnectorNode = tree.iter('connector')
    for node in ConnectorNode:
        threadInfo = node.find("threadInfo")
        reqInfo = node.find("requestInfo")

        connector_feature_attributes = feature.TomcatConnectorFeature(
            node.get("name"),
            threadInfo.get("maxThreads"),
            threadInfo.get("currentThreadCount"),
            threadInfo.get("currentThreadsBusy"),
            reqInfo.get("maxTime"),
            reqInfo.get("processingTime"),
            reqInfo.get("requestCount"),
            reqInfo.get("errorCount"),
            reqInfo.get("bytesReceived"),
            reqInfo.get("bytesSent")
        )
        yield('tomcat_connector', connector_feature_attributes, feature_type)

        workNode = node.iter("worker")
        for work in workNode:
            worker_feature_attributes = feature.TomcatWorkerFeature(
                node.get("name"),
                work.get("stage"),
                work.get("requestProcessingTime"),
                work.get("requestBytesSent"),
                work.get("requestBytesReceived"),
                work.get("remoteAddr"),
                work.get("virtualHost"),
                work.get("currentUri")
            )
            yield('tomcat_worker', worker_feature_attributes, feature_type)
