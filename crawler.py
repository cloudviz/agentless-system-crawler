#!/usr/bin/python

##
## (c) Copyright IBM Corp.2014,2015
##
## Wrapper around the crawlutils module that provides:
## (a) a network pull mode via an HTTP REST interface, and
## (b) an autonomous push mode via command-line invocation
##

import os
import sys
import socket
import crawlutils
import logging
import logging.handlers
import psutil
import time
import simplejson as json
import traceback
import multiprocessing
import tempfile
import csv
from collections import namedtuple
import argparse
import bottle

app = bottle.Bottle()

CRAWLER_HOST = crawlutils.get_host_ipaddr()
CRAWLER_PORT = 9999

logger = None

# This diect keeps track of active snapshot tasks on this host
tasks = {}

# this string should be same as the contents of the README.API file
apihelp = '''

Crawler API
-----------

1. /getsnapshot[?features=FEATURES][&since=SINCE]

   Returns a snapshot of FEATURES touched since SINCE as a text/csv stream.
   
   FEATURES is a comma-separated list of one or more of these feature-types:
      os,disk,process,connection,metric,file,config,package.
   It defaults to os,disk,process,connection.

   SINCE is one of BOOT,EPOCH. It defaults to BOOT.

   Example: /getsnapshot?features=process,connection

2. /snapshot[?url=URL][&namespace=NAMESPACE][&features=FEATURES][&since=SINCE][&frequency=FREQUENCY][&compress=COMPRESS]

   Emits a snapshot of FEATURES to URL every FREQUENCY seconds.
   
   SINCE limits the features to those touched since EPOCH,BOOT,LASTSNAPSHOT. It defaults to BOOT.
   
   COMPRESS is one of true,false and determines whether to gzip-compress the output data. It defaults to true.

   If FEATURES includes "file" or "config" you can optionally provide additional JSON options in the HTTP POST body.
   These default to:
      { 
         "file": {"root_dir": "/", "exclude_dirs": ["boot","dev","proc","sys","mnt","tmp"]},
         "config": {"root_dir": "/", "known_config_files": ["etc/passwd","etc/hosts","etc/mtab","etc/group"],
                    "discover_config_files": true}
      }
    
    Example: /snapshot?url=http://foo/bar&features=process,connection,metric&frequency=60

3. /status

   Returns a JSON dictionary of active snapshot tasks

4. /abort/ID
   
   Attempts to terminate snapshot task ID

5. /help
   
   Show this API help
'''

# return API help
@app.route("/")
@app.route("/help")
def help():
    bottle.response.content_type = 'text/plain'
    return apihelp
        

# asynchronous call that emits the snapshot data to a specified url, or to the local file system
@app.route("/snapshot", methods=['GET','POST'])
def snapshot():
    logger.debug('Received snapshot request')
    bottle.response.content_type = 'application/json'
    try:
        args = {}
        try:
            crawl_options = json.loads(bottle.request.body()) #flask.request.get_json(force=True)
            if crawl_options:
                args['options'] = crawl_options
        except:
            pass # benign- no json payload found in the request
        if bottle.request.query:
            value = bottle.request.query.get('url', None)
            if value:
                args['url'] = value
            value = bottle.request.query.get('namespace', None)
            if value:
                args['namespace'] = value
            value = bottle.request.query.get('features', None)
            if value: 
                args['features'] = value
            value = bottle.request.query.get('since', None)
            if value and value in ['EPOCH','BOOT','LASTSNAPSHOT']: 
                args['since'] = value
            value = bottle.request.query.get('frequency', None)
            if value:
                try:
                    args['frequency'] = int(value)
                except:
                    pass # ignore non-integer frequency value
            value = bottle.request.query.get('compress', None)
            if value and value in ['true','false']: 
                args['compress'] = value
        if 'url' not in args:
            return json.dumps({'success': False, 'message': 'URL argument is mandatory'}, indent=2)
        # invoke crawlutils as a separate process so this method can be asynchronous
        p = multiprocessing.Process(target=crawlutils.snapshot, kwargs=args)
        p.daemon = True
        p.start()
        tasks[p.pid] = {'process': p, 'args': args}
        logger.debug('Snapshot request completed successfully')
        return json.dumps({'success': True, 'ID': p.pid, 'arguments': args}, indent=2)
    except:
        return json.dumps({'success': False, 'exception': traceback.format_exc().split('\n')}, indent=2)

# synchronous call that returns the snapshot data to the caller as a text/csv stream
@app.route("/getsnapshot", methods=['GET','POST'])
def getsnapshot():
    logger.debug('Received getsnapshot request')
    framefile = tempfile.mktemp(prefix='frame.')
    try:
        args = {}
        try:
            crawl_options = json.loads(bottle.request.body())
            if crawl_options:
                args['options'] = crawl_options
        except:
            pass # benign- no json payload found in the request
        if bottle.request.query:
            value = bottle.request.query.get('features', None)
            if value: 
                args['features'] = value
            value = bottle.request.query.get('since', None)
            if value and value in ['EPOCH','BOOT','LASTSNAPSHOT']: 
                args['since'] = value
        args['url'] = 'file://{0}'.format(framefile) 
        args['compress'] = False
        crawlutils.snapshot(**args)
        bottle.response.content_type = 'text/csv'
        with open(framefile, 'r') as fd:
            for line in fd:
                yield line
        os.remove(framefile)
    except:
        if os.path.exists(framefile):
            os.remove(framefile)
        bottle.response.content_type = 'application/json'
        yield json.dumps({'success': False, 'stacktrace': traceback.format_exc().split('\n')}, indent=2)


# returns the list of snapshot task IDs
@app.route("/status")
def status():
    bottle.response.content_type = 'application/json'
    try:
        active_tasks = []
        for tid in tasks.keys():
            entry = tasks.get(tid, None)
            if entry:
                if tasks[tid]['process'].is_alive():
                    active_tasks.append({'ID': tid, 'arguments': tasks[tid]['args']})
                else:
                    try:
                        del tasks[tid]
                    except:
                        pass # ignore, since another thread may have deleted this entry
        return json.dumps({'success': True, 'tasks': active_tasks}, indent=2)
    except:
        return json.dumps({'success': False, 'stacktrace': traceback.format_exc().split('\n')}, indent=2)


# attempts to abort an active snapshot task
@app.route("/abort/<ID:int>")
def abort(ID):
    bottle.response.content_type = 'application/json'
    try:
        entry = tasks.get(ID, None)
        if entry:
            proc = entry['process']
            if proc.is_alive():
                proc.terminate()
            return json.dumps({'success': True}, indent=2)
        else:
            return json.dumps({'success': False, 'message': 'ID {0} is invalid, or this snapshot task has already terminated'.format(ID)}, indent=2)
    except:
        return json.dumps({'success': False, 'stacktrace': traceback.format_exc().split('\n')}, indent=2)


def setup_logger(logger_name, logfile='crawler.log', process_id=None):
    _logger = logging.getLogger(logger_name)
    _logger.setLevel(logging.DEBUG)
    logfile_name, logfile_xtnsion = os.path.splitext(logfile)
    if process_id == None:
        fname = logfile
    else:
        fname = '{0}-{1}{2}'.format(logfile_name, process_id, logfile_xtnsion)
    h = logging.handlers.RotatingFileHandler(
            filename=fname, maxBytes=10e6, backupCount=1)
    f = logging.Formatter(
            '%(asctime)s %(processName)-10s %(levelname)-8s %(message)s')
    h.setFormatter(f)
    _logger.addHandler(h)


def crawler_worker(process_id, logfile, snapshot_params):
    setup_logger("crawlutils", logfile, process_id)
    crawlutils.snapshot(**snapshot_params)


## (b) an autonomous push mode via command-line invocation
def start_autonomous_crawler(snapshot_params, process_count, logfile):

    params['parent_pid'] = int(os.getpid())
    if params['crawlmode'] == 'OUTCONTAINER':
        jobs = []

        for index in xrange(process_count):
            params['process_id'] = index
            params['process_count'] = process_count
            p = multiprocessing.Process(name="crawler-%s" % (index),
                            target=crawler_worker,
                            args=(index, logfile, snapshot_params))
            jobs.append((p, index))
            p.start()
            logger.info("Crawler %s (pid=%s) started", index, p.pid)

        """
        Monitor the children. The behavior is to wait for all children to
        terminate, or to exit and raise an exception when any of the processes
        crashes.
        """
        while jobs:
            for index, (job, process_id) in enumerate(jobs):
                if not job.is_alive():
                    exitcode = job.exitcode
                    pname = job.name
                    pid = job.pid
                    if job.exitcode:
                        logger.info("%s terminated unexpectedly with "
                                    "errorcode %s" % (pname, exitcode))
                        for other_job, process_id in jobs:
                            if other_job != job:
                                logger.info("Terminating crawler %s (pid=%s)",
                                            process_id, other_job.pid)
                                os.kill(other_job.pid, 9)
                        logger.info("Exiting as all jobs were terminated.")
                        raise RuntimeError("%s terminated unexpectedly with "
                                           "errorcode %s" % (pname, exitcode))
                    else:
                        logger.info("Crawler %s (pid=%s) exited normally.",
                                    process_id, pid)
                    del jobs[index]
            time.sleep(0.1)
        logger.info("Exiting as there are no more processes running.")
    else:
        # INVM, OUTVM, and others
        setup_logger("crawlutils", logfile, 0)
        crawlutils.snapshot(**params)


# Main listen/exec loop

if __name__ == '__main__':
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser()
        parser.add_argument('--url', dest="url", type=str, nargs="+", default=None, help='Send the snapshot data to URL. Defaults to file://frame')
        parser.add_argument('--namespace', dest="namespace", type=str, nargs="?", default=None, help='Data source this crawler is associated with. Defaults to /localhost')
        parser.add_argument('--features', dest="features", type=str, default=None, help='Comma-separated list of feature-types to crawl. Defaults to {0}'.format(crawlutils.DEFAULT_FEATURES_TO_CRAWL))
        parser.add_argument('--since', dest="since", type=str, choices=['EPOCH','BOOT','LASTSNAPSHOT'], default=None, help='Only crawl features touched since {EPOCH,BOOT,LASTSNAPSHOT}. Defaults to BOOT')
        parser.add_argument('--frequency', dest="frequency", type=int, default=None, help='Interval in secs between successive snapshots. Defaults to -1')
        parser.add_argument('--compress', dest="compress", type=str, choices=['true','false'], default=None, help='Whether to GZIP-compress the output frame data, must be one of {true,false}. Defaults to true')
        parser.add_argument('--logfile', dest="logfile", type=str, default="crawler.log", help='Logfile path. Defaults to crawler.log')
        parser.add_argument('--options', dest="options", type=str, default=None, help="JSON dict of crawler options (see README for defaults)")
        parser.add_argument('--maxfeatures', dest="maxfeatures", type=str, default=None, help='Maximum number of features to emit')
        parser.add_argument('--crawlmode', dest="crawlmode", type=str,
            choices=['INVM','OUTVM','MOUNTPOINT','DEVICE','FILE','ISCSI','OUTCONTAINER'],
            default='INVM', help='The crawler mode: {INVM,OUTVM,MOUNTPOINT,'
            'DEVICE,FILE,ISCSI}. Defaults to INVM')
        parser.add_argument('--mountpoint', dest="mountpoint", type=str, default=None, help='Mountpoint location (required for --crawlmode MOUNTPOINT)')
        parser.add_argument('--inputfile', dest="inputfile", type=str, default=None, help='Path to file that contains frame data (required for --crawlmode FILE)')
        parser.add_argument('--format', dest="format", type=str, default="csv",
            choices=['csv','graphite'], help='Emitted data format.')
        parser.add_argument('--crawlContainers', dest="crawlContainers",
            type=str, nargs="?", default=None, help='List of containers to '
            'crawl as a list of Docker container IDs. If this is not passed, '
            'then just the host is crawled. Alternatively the word "ALL" can '
            'be used to crawl every container. "ALL" will crawl all namespaces'
            ' including the host itself. This option is only valid for INVM '
            'crawl mode. Example: --crawlContainers 5f3380d2319e,681be3e32661')
        parser.add_argument('--vmDomains', dest="vmDomains", type=str,
            nargs="?", default=None, help='Space separated list of VMs '
            'to crawl. If this argument is not passed, then no VM is crawled. '
            'Alternatively the word "ALL" can be used to crawl every VM. "ALL"'
            ' will NOT crawl the hypervisor. ' 'This option is only valid for '
            'OUTVM crawl mode. The format of each item is "[instance-name]" or'
            ' "[instance-name],[arch],[linux-kernel-version]" Example: '
            '--vmDomain "instance-1,x86_64,3.3.3" "instance-2,x86_64,2.6.5"')
        parser.add_argument('--environment', dest="environment", type=str,
            default="cloudsight", choices=['cloudsight', 'alchemy'],
            help='If given, this argument is used to specify how to set the VMs'
            ' or containers namespaces.')
        parser.add_argument('--maxRetries', dest="maxRetries", type=int,
            default=None, help='Maximum number of retries when sending data to'
            ' kafka or the cloudsight broker. The waiting between retries is '
            'this exponential backoff: (2^retries * 100) milliseconds')
        parser.add_argument('--numprocesses', dest="numprocesses", type=int,
            default=None, help = 'Number of processes used for container '
                                 'crawling. Defaults to the number of cores.')
        parser.add_argument('--extraMetadataFile', dest="extraMetadataFile",
            type=str, default=None, help='Json file with data to be annotate '
            'all features. It can be used to append a set of system identifiers'
            ' to the metadata feature and if the --extraMetadataForAll')
        parser.add_argument('--extraMetadataForAll', dest='extraMetadataForAll',
            action='store_true', default=False, help='If specified all features'
            ' are appended with extra metadata.')
        parser.add_argument('--linkContainerLogFiles', dest='linkContainerLogFiles',
            action='store_true', default=False, help='If specified and if'
            ' running in OUTCONTAINER mode, then the crawler maintains links to'
            ' container log files.')

        args  = parser.parse_args()
        params = {}
        if args.url:
            params['urls'] = args.url
        if args.namespace:
            params['namespace'] = args.namespace
        if args.features:
            params['features'] = args.features
        if args.since:
            params['since'] = args.since
        if args.frequency:
            params['frequency'] = args.frequency
        if args.compress:
            if args.compress == 'true':
                compress = True
            else:
                compress = False
            params['compress'] = compress
        if args.options:
            params['options'] = json.loads(args.options)
        if args.maxfeatures:
            params['maxfeatures'] = json.loads(args.maxfeatures)
            raise Exception("maxfeatures is not implemented, look at issue #291")
        if args.crawlmode:
            params['crawlmode'] = args.crawlmode
            if args.crawlmode == 'MOUNTPOINT':
                if args.mountpoint:
                    params['mountpoint'] = args.mountpoint
                else:
                    print 'Need to specify mountpoint location (--mountpoint) for MOUNTPOINT mode'
                    sys.exit(1)
            elif args.crawlmode == 'DEVICE':
                    print 'NOT IMPLEMENTED! Will Need to specify device location for DEVICE mode'
                    sys.exit(1)
            elif args.crawlmode == 'FILE':
                if args.inputfile:
                    params['inputfile'] = args.inputfile
                else:
                    print 'Need to specify frame file location (--inputfile) for FILE mode'
                    sys.exit(1)
            elif args.crawlmode == 'ISCSI':
                    print 'NOT IMPLEMENTED! Will Need to somehow specify connection info for ISCSI mode'
                    sys.exit(1)
            if args.crawlmode == 'OUTVM':
                if args.vmDomains:
                    params['libvirt_domains_list'] = args.vmDomains
                else:
                    print('Need to specify list of domains to crawl '
                          '(--vmDomains) for OUTVM mode. Or ALL at least.')
                    sys.exit(1)
            if args.crawlmode == 'OUTCONTAINER':
                if args.crawlContainers:
                    params['docker_containers_list'] = args.crawlContainers
                if not args.numprocesses:
                    args.numprocesses = multiprocessing.cpu_count()
                params['link_container_log_files'] = args.linkContainerLogFiles
        if args.format:
            params['format'] = args.format
        if args.environment:
            params['environment'] = args.environment
        if args.maxRetries:
            params['max_retries'] = args.maxRetries
        if args.extraMetadataFile:
            try:
                with open(args.extraMetadataFile, 'r') as fp:
                    params['extra_metadata'] = fp.read()
            except Exception, e:
                print('Could not read the feature metadata json file: %s' % e)
                sys.exit(1)
            if args.extraMetadataForAll:
                params['extra_metadata_for_all'] = args.extraMetadataForAll

        setup_logger("crawler-main", args.logfile)
        logger = logging.getLogger("crawler-main")
        logger.info('Starting crawler at {0}'.format(CRAWLER_HOST))

        start_autonomous_crawler(params, args.numprocesses, args.logfile)
    else:
        print ''
        print 'Starting crawler at URL http://{0}:{1}'.format(CRAWLER_HOST, CRAWLER_PORT)
        print 'Log output will be in /var/log/crawler.log'
        print ''
        logging.basicConfig(filename='/var/log/crawler.log', filemode='w', format='%(asctime)s %(levelname)s : %(message)s', level=logging.DEBUG)
        logger = logging.getLogger(__name__)
        logger.info('Started crawler at URL http://{0}:{1}'.format(CRAWLER_HOST, CRAWLER_PORT))
        logger.info('Log output will be in /var/log/crawler.log')
        app.run(host=CRAWLER_HOST, port=CRAWLER_PORT, quiet=True)


# Example Usage #1: crawl all features with default options
'''
crawlutils.snapshot()
'''

# Example Usage #2: crawl selected features with custom options, emit frame to local file
'''
my_crawl_commands = [
    ('os', None), ('disk', None), ('process', None), ('connection', None), # these features don't take options
    ('file', {'root_dir':'/', 'exclude_dirs':['boot', 'dev', 'mnt', 'proc', 'sys']}),
    ('config', {'root_dir':'/', 'known_config_files':['etc/passwd', 'etc/hosts', 'etc/issue', 'etc/mtab', 'etc/group'], 'discover_config_files': True})
]
crawlutils.snapshot(emit_to_url='file://frame.csv', crawl_commands=my_crawl_commands)
'''

# Example Usage #3 (UDeploy use case): crawl "file" features and use a customer root_dir_alias, emit frame to local file
'''
my_crawl_commands = [
    ('file', {'root_dir':'/etc/tomcat6', 'root_dir_alias':'@tomcat'}),
    ('file', {'root_dir':'/var/log/tomcat6', 'root_dir_alias':'@tomcat-logs'}),
    ('file', {'root_dir':'/usr/share/tomcat6', 'root_dir_alias':'@tomcat-webapps'}),
    ('config', {'root_dir':'/etc/tomcat6', 'root_dir_alias':'@tomcat', 'discover_config_files':True}),
    ('config', {'root_dir':'/usr/share/tomcat6', 'root_dir_alias':'@tomcat-webapps', 'discover_config_files':True}),
    ('config', {'root_dir':'/', 'known_config_files':['etc/passwd', 'etc/group']}),
]
crawlutils.snapshot(emit_to_url='file://frame.csv', crawl_commands=my_crawl_commands)
'''    
    
        
