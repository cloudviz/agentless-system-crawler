import os
import sys
import inspect
import imp
import time
import argparse
import shutil
import cStringIO
import json
from icrawl_plugin import IContainerCrawler

plugins_dir = '/crawler/plugins/systems/' # might eventually become /home/user1/crawler/plugins/...
guestcont_plugins_file = '/rootfs_local/crawlplugins'
plugins_file = '/rootfs_local/crawlplugins' # should eventually be /home/user1/crawlplugins
frame_dir = '/home/user1/features/'
plugin_objs = []
active_plugins = []
frquency = -1
next_iteration_time = None

def get_plugin_obj(plugin_name):
    plugin_module_name = plugin_name.strip()+'_container_crawler'
    plugin_filename = plugin_name.strip()+'_container_crawler.py'
    for filename in os.listdir(plugins_dir):
        if plugin_filename == filename:
            plugin_module = imp.load_source(plugin_module_name, plugins_dir+plugin_filename)
            plugin_classes = inspect.getmembers(plugin_module, inspect.isclass)
            for plugin_class_name, plugin_class in plugin_classes:
                if plugin_class_name is not 'IContainerCrawler' and issubclass(plugin_class, IContainerCrawler):
                    plugin_obj = plugin_class()
                    return plugin_obj
            break

def run_plugins_org():
    # import pdb
    # pdb.set_trace()
    plugin_names = tuple(open('/crawlercmd/crawlplugins','r'))
    for plugin_name in plugin_names:
        print plugin_name
        plugin_obj = get_plugin_obj(plugin_name)
        print plugin_obj.get_feature()
        try:
            for i in plugin_obj.crawl('some_cont_id',avoid_setns=False):
                print i
        except:
            print sys.exc_info()[0]

def parse_args():
    global frequency
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--frequency',
        dest='frequency',
        type=int,
        default=-1,
        help='Target time period for iterations. Defaults to -1 which '
             'means only run one iteration.'
    )
    args = parser.parse_args()
    frequency = args.frequency

def _get_next_iteration_time(snapshot_time):
    """
    Returns the number of seconds to sleep before the next iteration.
    :param snapshot_time: Start timestamp of the current iteration.
    :return: Seconds to sleep as a float.
    """
    global next_iteration_time
    if frequency == 0:
        return 0
    
    if next_iteration_time is None:
        next_iteration_time = snapshot_time + frequency
    else:
        next_iteration_time += frequency

    while next_iteration_time + frequency < time.time():
        next_iteration_time += frequency

    time_to_sleep = next_iteration_time - time.time()
    return time_to_sleep

def format(frame):
    """
    Writes frame data and metadata into iostream in csv format.

    :param iostream: a CStringIO used to buffer the formatted features.
    :param frame: a BaseFrame object to be written into iostream
    :return: None
    """
    iostream = cStringIO.StringIO()
    for (key, val, feature_type) in frame:
        if not isinstance(val, dict):
            val = val._asdict()
        iostream.write('%s\t%s\t%s\n' % (
            feature_type, json.dumps(key),
            json.dumps(val, separators=(',', ':'))))
    return iostream

def iterate(snapshot_time=0, timeout=0):
    if timeout > 0:
        time.sleep(timeout)
    try:
        reload_plugins()
        frame_file = frame_dir+str(int(snapshot_time))
        fd = open(frame_file,'w')
        for plugin_obj in plugin_objs:
            plugin_crawl_output = plugin_obj.crawl('some_cont_id',avoid_setns=False)
            iostream = format(plugin_crawl_output)
            iostream.seek(0)
            shutil.copyfileobj(iostream, fd)
        fd.close()
    except:
        print sys.exc_info()[0]

def run_plugins():
    if os.path.isdir(frame_dir):
        shutil.rmtree(frame_dir)
    os.makedirs(frame_dir)
    time_to_sleep = 0
    while True:
        snapshot_time = time.time()
        iterate(snapshot_time,time_to_sleep)
        # Frequency < 0 means only one run.
        if frequency < 0:
            break
        time_to_sleep = _get_next_iteration_time(snapshot_time)

def get_plugin_external(url):
    # download tar or .plugin+.py files from url
    # put inside plugins_dir == crawler/plugins/
    # do pip install requirements.txt for plugin
    # add plugin name to plugins_file /home/user1/crawlplugins
    # TODO
    pass

def get_plugin_local(plugin_name):
    # collect plugin using plugin_name from a central crawler-specific repo.
    # put inside plugins_dir == crawler/plugins/ 
    # do pip install requirements.txt for plugin
    # add plugin name to plugins_file /home/user1/crawlplugins
    # central repo plugins can also be preloaded in plugin cont
    # TODO
    pass

def gather_plugins():
    if not os.path.exists(guestcont_plugins_file):
        return

    fd = open(guestcont_plugins_file,'r')
    for plugin_line in fd.readlines():
        if plugin_line.startswith('http'):
            get_plugin_external(plugin_line)	
        else:
            get_plugin_local(plugin_line)
    fd.close()

    global plugin_objs 
    global active_plugins 
    plugin_names = tuple(open(plugins_file,'r'))
    for plugin_name in plugin_names:
        if plugin_name in active_plugins:
            continue
        plugin_obj = get_plugin_obj(plugin_name)
        if plugin_obj is not None:
            print plugin_name, plugin_obj.get_feature()
            plugin_objs.append(plugin_obj)
            active_plugins.append(plugin_name)

def reload_plugins():
    gather_plugins()

def sleep_forever():
    while True:
        time.sleep(10)
 
parse_args()
gather_plugins()
run_plugins()
sleep_forever()
