import os

plugin_names = tuple(open('/crawlercmd/crawlplugins','r'))
for plugin_name in plugin_names:
    plugin_file = plugin_name.strip()+'_container_crawler.py'
    plugin_module = plugin_name.strip()+'_container_crawler'
    for filename in os.listdir('/crawler/crawler/plugins/systems'):
        if filename == plugin_file:
            print filename
            import plugin_module

