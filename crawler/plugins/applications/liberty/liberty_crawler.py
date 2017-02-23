import urllib2
import ssl
import json
import re
from plugins.applications.liberty import feature
from utils.crawler_exceptions import CrawlError


def retrieve_status_page(user, password, url):

    try:
        ssl._create_unverified_context
    except AttributeError:
        pass
    else:
        ssl._create_default_https_context = ssl._create_unverified_context

    password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
    password_mgr.add_password(None, url, user, password)
    handler = urllib2.HTTPBasicAuthHandler(password_mgr)
    opener = urllib2.build_opener(handler)
    urllib2.install_opener(opener)

    req = urllib2.Request(url)
    try:
        response = urllib2.urlopen(req)
        return response.read()
    except Exception:
        raise CrawlError("can't access to http://%s", url)


def get_url(json_array, className):
    urllist = []

    for each_json in json_array:
        if each_json.get("className") == className:
            urllist.append(each_json.get("URL"))

    return urllist


def get_url_and_name(json_array, className):
    url_name_list = []
    r = re.compile("name=(.+)")
    for each_json in json_array:

        if each_json.get("className") == className:
            m = r.search(each_json.get("objectName"))
            url_name_list.append([each_json.get("URL"), m.group(1)])

    return url_name_list


def servlet_get_url(attribute_array, name):
    for attribute in attribute_array:
        if attribute.get("name") == name:
            return attribute.get("URL")


def get_servlet_stats(base_url, url, user, password):
    monitor_status = json.loads(retrieve_status_page(
                                user, password, base_url+url))
    serv_stats = {}

    attribute_array = monitor_status.get("attributes")
    servlet_url = servlet_get_url(attribute_array, "ResponseTimeDetails")
    servlet_status = json.loads(retrieve_status_page(
                                user, password, base_url+servlet_url))

    serv_stats["reqCount"] = servlet_status.get("value").get("count")
    serv_stats["responseMean"] = servlet_status.get("value").get("mean")
    serv_stats["responseMax"] = servlet_status.get("value").get("maximumValue")
    serv_stats["responseMin"] = servlet_status.get("value").get("minimumValue")

    servlet_url = servlet_get_url(attribute_array, "ServletName")
    servlet_status = json.loads(retrieve_status_page(
                                user, password, base_url + servlet_url))
    serv_stats["name"] = servlet_status.get("value")

    servlet_url = servlet_get_url(attribute_array, "AppName")
    servlet_status = json.loads(retrieve_status_page(
                                user, password, base_url + servlet_url))
    serv_stats["appName"] = servlet_status.get("value")
    return serv_stats


def get_jvm_stats(base_url, url, user, password):
    monitor_status = json.loads(retrieve_status_page(
                                user, password, base_url+url))
    jvm_stats = {}

    attribute_array = monitor_status.get("attributes")
    stats_name_array = ["Heap", "FreeMemory", "UsedMemory",
                        "ProcessCPU", "GcCount", "GcTime", "UpTime"]
    for stat_name in stats_name_array:
        jvm_url = servlet_get_url(attribute_array, stat_name)
        jvm_status = json.loads(retrieve_status_page(
                                user, password, base_url+jvm_url))
        jvm_stats[stat_name] = jvm_status.get("value")

    return jvm_stats


def get_thread_stats(base_url, url, user, password):
    monitor_status = json.loads(retrieve_status_page(
                                user, password, base_url+url))
    thread_stats = {}

    attribute_array = monitor_status.get("attributes")
    stats_name_array = ["ActiveThreads", "PoolSize", "PoolName"]
    for stat_name in stats_name_array:
        thread_url = servlet_get_url(attribute_array, stat_name)
        thread_status = json.loads(retrieve_status_page(
                                   user, password, base_url+thread_url))
        thread_stats[stat_name] = thread_status.get("value")

    return thread_stats


def get_session_stats(base_url, url, user, password):
    monitor_status = json.loads(retrieve_status_page(
                                user, password, base_url+url))
    session_stats = {}

    attribute_array = monitor_status.get("attributes")
    session_name_array = ["CreateCount", "LiveCount", "ActiveCount",
                          "InvalidatedCount", "InvalidatedCountbyTimeout"]
    for stat_name in session_name_array:
        session_url = servlet_get_url(attribute_array, stat_name)
        session_status = json.loads(retrieve_status_page(
                                    user, password, base_url+session_url))
        session_stats[stat_name] = session_status.get("value")

    return session_stats


def retrieve_metrics(host='localhost', port=9443,
                     user='user', password='password',
                     feature_type='application'):
    url = "https://%s:%s/IBMJMXConnectorREST/mbeans/" % (host, port)

    status = retrieve_status_page(user, password, url)
    json_obj = json.loads(status)
    base_url = "https://%s:%s" % (host, port)

    mbeans_url_array = get_url(json_obj,
                               "com.ibm.ws.webcontainer.monitor.ServletStats")
    for url in mbeans_url_array:
        serv_stats = get_servlet_stats(base_url, url, user, password)
        servlet_attributes = feature.LibertyServletFeature(
            serv_stats.get("name"),
            serv_stats.get("appName"),
            serv_stats.get("reqCount"),
            serv_stats.get("responseMean"),
            serv_stats.get("responseMax"),
            serv_stats.get("responseMin")
        )
        yield ('liberty_servlet_status', servlet_attributes, feature_type)

    mbeans_url_array = get_url(json_obj, "com.ibm.ws.monitors.helper.JvmStats")

    for url in mbeans_url_array:
        jvm_stats = get_jvm_stats(base_url, url, user, password)
        jvm_attributes = feature.LibertyJVMFeature(
            jvm_stats.get("Heap"),
            jvm_stats.get("FreeMemory"),
            jvm_stats.get("UsedMemory"),
            jvm_stats.get("ProcessCPU"),
            jvm_stats.get("GcCount"),
            jvm_stats.get("GcTime"),
            jvm_stats.get("UpTime")
        )
        yield ('liberty_jvm_status', jvm_attributes, feature_type)

    mbeans_url_array = get_url(json_obj,
                               "com.ibm.ws.monitors.helper.ThreadPoolStats")

    for url in mbeans_url_array:
        thread_stats = get_thread_stats(base_url, url, user, password)
        thread_attributes = feature.LibertyThreadFeature(
            thread_stats.get("ActiveThreads"),
            thread_stats.get("PoolSize"),
            thread_stats.get("PoolName")
        )
        yield ('liberty_thread_status', thread_attributes, feature_type)

    mbeans_url_name_array = get_url_and_name(json_obj,
                                             "com.ibm.ws.session.monitor"
                                             ".SessionStats")

    for url_name in mbeans_url_name_array:
        session_stats = get_session_stats(base_url,
                                          url_name[0], user, password)
        session_attributes = feature.LibertySessionFeature(
            url_name[1],
            session_stats.get("CreateCount"),
            session_stats.get("LiveCount"),
            session_stats.get("ActiveCount"),
            session_stats.get("InvalidatedCount"),
            session_stats.get("InvalidatedCountbyTimeout"),
        )
        yield ('liberty_session_status', session_attributes, feature_type)
