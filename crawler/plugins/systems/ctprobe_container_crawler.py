
import errno
import glob
import json
import logging
import os
import pwd
import signal
import time

from collections import namedtuple

import netifaces
import psutil
import utils.dockerutils
import requests_unixsocket

from icrawl_plugin import IContainerCrawler
from utils.ethtool import ethtool_get_peer_ifindex
from utils.namespace import run_as_another_namespace
from utils.process_utils import start_child
from utils.socket_utils import if_indextoname

logger = logging.getLogger('crawlutils')

PeerInterface = namedtuple('PeerInterface', ['peer_ifindex', 'ip_addresses'])
NetlinkFeature = namedtuple('NetlinkFeature', ['data'])

DEFAULT_UNIX_PATH = '/var/run/conntrackprobe.sock'


class ConntrackProbeClient(object):
    """ Client class for talking to the conntrack probe """
    def __init__(self, sockpath=DEFAULT_UNIX_PATH):
        self.sockpath = sockpath

    def add_collector(self, url, ipaddresses, ifname):
        """
          Add a collector for the given IP addresses and tied to the given
          interface.
        """
        code, content = self.send_request('add_collector',
                                          [url, ipaddresses, ifname])
        if code == 200:
            return True
        else:
            raise Exception('HTTP Error %d: %s' % (code, content['error']))

    def send_request(self, method, params):
        req = {
            'jsonrpc': '2.0',
            'method': method,
            'params': params,
            'id': 1,
        }
        sp = self.sockpath.replace('/', '%2f')
        session = requests_unixsocket.Session()
        r = session.get('http+unix://%s' % sp, data=json.dumps(req))

        return r.status_code, json.loads(r.content)


class CTProbeContainerCrawler(IContainerCrawler):
    # Class for acquiring netlink data via a conntrackprobe

    BIND_ADDRESS = '127.0.0.1'
    STALE_FILE_TIMEOUT = 3600

    # whether the conntrackprobe process has been started
    ctprobe_pid = 0

    # Interfaces for which conntrackprobe has been configured.
    # This is a list of interfaces for which conntrackprobe
    # has been configured.
    ifaces_monitored = []

    # Since we don't get notified when a container dies
    # we need to periodically check the interfaces on the host
    # against those in ctprobes_monitored.
    next_cleanup = 0

    def get_feature(self):
        return 'ctprobe'

    def setup_outputdir(self, output_dir, uid, gid):
        """
          If necessary create or change ownership of the output directory.
        """
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as ex:
                logger.error('Could not created dir %s : %s' %
                             (output_dir, str(ex)))
                return False

        try:
            os.chown(output_dir, uid, gid)
        except Exception as ex:
            logger.error('Could not change ownership of %s: %s' %
                         (output_dir, str(ex)))
            return False

        return True

    def _get_user(self, **kwargs):
        """ Get the deprivileged user we are supposed to use """
        ctprobe_user = kwargs.get('ctprobe_user', 'nobody')
        try:
            passwd = pwd.getpwnam(ctprobe_user)
            return ctprobe_user, passwd
        except Exception as ex:
            logger.error('Could not find user %s on this system: %s' %
                         (ctprobe_user, ex))
            return ctprobe_user, None

    def start_ctprobe(self, sockpath=DEFAULT_UNIX_PATH, **kwargs):
        """
          Start the conntrackprobe process;
          use the bindaddr and port as the collector.
          This function returns the process ID of the started process
          and an errcode (errno) in case an error was encountered in
          the start_child function.
        """
        ctprobe_user, passwd = self._get_user(**kwargs)
        if not passwd:
            return -1, errno.ENOENT

        params = ['conntrackprobe',
                  '--unix', sockpath,
                  '--user', ctprobe_user,
                  '--logfile', '/var/log/conntrackprobe.log']

        try:
            pid, errcode = start_child(params, [], [0, 1, 2],
                                       [],
                                       setsid=False,
                                       max_close_fd=128)
            logger.info('Started conntrackprobe as pid %d' % pid)
        except Exception:
            pid = -1
            errcode = errno.EINVAL

        return pid, errcode

    def terminate_ctprobe(self, pid):
        """
          Terminate the conntrackprobe process given its PID
        """
        proc = psutil.Process(pid=pid)
        if proc and proc.name() == 'conntrackprobe':
            os.kill(pid, signal.SIGKILL)
        CTProbeContainerCrawler.ifaces_monitored = []

    def check_ctprobe_alive(self, pid):
        """
          Check whether the conntrackprobe with the given PID is still running
          Returns True if the conntrackprobe is still alive, false otherwise.
        """
        gone = False
        try:
            proc = psutil.Process(pid=pid)
            if not proc or proc.name() != 'conntrackprobe':
                gone = True
        except Exception:
            gone = True

        if gone:
            CTProbeContainerCrawler.ifaces_monitored = []
        return not gone

    def configure_ctprobe(self, ipaddresses, ifname, filepath, **kwargs):
        """
          Configure the CTprobe to listen for data from the current
          container and have it write the data to files specific to
          that container.
        """
        coll = 'file+json://%s' % filepath

        cpc = ConntrackProbeClient(DEFAULT_UNIX_PATH)
        try:
            cpc.add_collector(coll, ipaddresses, ifname)
        except Exception as ex:
            logger.error('Could not add collector: %s' % ex)
            return False

        return True

    def start_netlink_collection(self, ifname, ip_addresses, container_id,
                                 **kwargs):
        """
          Start the collector and program conntrackprobe. Return False in case
          of an error, True otherwise
        """

        ctprobe_user, passwd = self._get_user(**kwargs)
        if not passwd:
            return False

        ctprobe_output_dir = kwargs.get('ctprobe_output_dir',
                                        '/tmp/crawler-ctprobe')
        if not self.setup_outputdir(ctprobe_output_dir, passwd.pw_uid,
                                    passwd.pw_gid):
            return False

        filepattern = kwargs.get('output_filepattern',
                                 'conntrack-{ifname}-{timestamp}')
        filepath = '%s/%s' % (ctprobe_output_dir, filepattern)

        success = self.configure_ctprobe(ip_addresses, ifname,
                                         filepath, **kwargs)
        if not success:
            logger.warn('Terminating malfunctioning conntrackprobe')
            self.terminate_ctprobe(CTProbeContainerCrawler.ctprobe_pid)
            # setting the PID to zero will cause it to be restarted
            # upon next crawl()
            CTProbeContainerCrawler.ctprobe_pid = 0

        return success

    def cleanup(self, **kwargs):
        """
          Check the available interfaces on the host versus those ones we
          have flow probes running and remove those where the interface has
          disappeared. We clean up the files with netlink data that were
          written for those interfaces.
        """
        devices = netifaces.interfaces()

        lst = []

        for ifname in CTProbeContainerCrawler.ifaces_monitored:
            if ifname not in devices:
                self.remove_datafiles(ifname, **kwargs)
            else:
                lst.append(ifname)

        CTProbeContainerCrawler.ifaces_monitored = lst

    @classmethod
    def remove_old_files(cls, **kwargs):
        """
          Remove all old files that the crawler would never pick up.
        """
        now = time.time()
        output_dir = kwargs.get('ctprobe_output_dir', '/tmp/crawler-ctprobe')

        for filename in glob.glob('%s/*' % output_dir):
            try:
                statbuf = os.stat(filename)
                # files older than 1 hour are removed
                if statbuf.st_mtime + \
                        CTProbeContainerCrawler.STALE_FILE_TIMEOUT < now:
                    os.remove(filename)
            except Exception:
                continue

    def crawl(self, container_id, avoid_setns=False, **kwargs):
        """
          Start flow probe + data collector pairs on the interfaces of
          the given container; collect the files that the collector
          wrote and return their content.
        """
        if not self.check_ctprobe_alive(CTProbeContainerCrawler.ctprobe_pid):
            CTProbeContainerCrawler.ctprobe_pid = 0

        if CTProbeContainerCrawler.ctprobe_pid == 0:
            pid, errcode = self.start_ctprobe(**kwargs)
            CTProbeContainerCrawler.ctprobe_pid = pid
            if pid < 0:
                logger.info('Starting conntrackprobe failed: %s' %
                            errcode)

        if CTProbeContainerCrawler.ctprobe_pid < 0:
            return

        if time.time() > CTProbeContainerCrawler.next_cleanup:
            # we won't run the cleanup of old files the first time
            # but let the crawler do one full round of picking up
            # relevant files and then only we do a proper cleaning
            if CTProbeContainerCrawler.next_cleanup > 0:
                CTProbeContainerCrawler.remove_old_files(**kwargs)

            self.cleanup(**kwargs)
            CTProbeContainerCrawler.next_cleanup = time.time() + 30

        ifnames = self.start_container_ctprobes(container_id, avoid_setns,
                                                **kwargs)

        return self.collect_files(container_id, ifnames, **kwargs)

    def create_filenamepattern(self, **kwargs):
        """
          Create the filename pattern for the files where the
          socket-datacollector writes its data into.
        """
        output_dir = kwargs.get('ctprobe_output_dir', '/tmp/crawler-ctprobe')
        filepattern = kwargs.get('output_filepattern',
                                 'conntrack-{ifname}-{timestamp}')
        filenamepattern = os.path.join(output_dir, filepattern)

        return filenamepattern.format(**kwargs)

    def remove_datafiles(self, ifname, **kwargs):
        """
          Remove conntrack netlink data files that belong to an interface
        """
        kwargs.update({
            'container-id': '*',
            'ifname': ifname,
            'pid': '*',
            'timestamp': '*',
        })
        filenamepattern = self.create_filenamepattern(**kwargs)

        for filename in glob.glob(filenamepattern):
            try:
                os.remove(filename)
            except Exception:
                pass

    def collect_files(self, container_id, ifnames, **kwargs):
        """
          Collect the files with netlink data for the given interface
          and container_id;
          remove the files after reading their content
        """
        for ifname in ifnames:
            kwargs.update({
                'container-id': container_id,
                'ifname': ifname,
                'pid': '*',
                'timestamp': '*',
            })
            filenamepattern = self.create_filenamepattern(**kwargs)

            globs = glob.glob(filenamepattern)
            for filename in globs:
                # skip over files currently being written
                if filename.endswith(".tmp"):
                    continue
                try:
                    with open(filename, 'r') as f:
                        raw = f.read()
                    data = json.loads(raw)
                except Exception as ex:
                    logger.info('Error reading datafile: %s' % ex)
                    continue

                try:
                    os.remove(filename)
                except Exception as ex:
                    logger.info('Error removing datafile: %s' % ex)
                    continue

                feature_key = '{0}-{1}'.format('netlink', ifname)

                yield (feature_key, NetlinkFeature(
                    data
                ), 'netlink')

    def start_container_ctprobes(self, container_id, avoid_setns=False,
                                 **kwargs):
        """
          Unless flow probes are already running on the interfaces of the
          given container, we start them.
        """
        inspect = utils.dockerutils.exec_dockerinspect(container_id)
        state = inspect['State']
        pid = str(state['Pid'])

        if avoid_setns:
            raise NotImplementedError('avoidsetns mode not implemented')

        ifnames = []

        try:
            peers = run_as_another_namespace(pid,
                                             ['net'],
                                             self._crawl_in_system)
            for peer in peers or []:
                # in rare cases we get an interface without IP address
                # assigned ot it, yet; we skip it for now and try again
                # on the next crawl
                if len(peer.ip_addresses) == 0:
                    continue

                try:
                    ifname = if_indextoname(peer.peer_ifindex)
                except Exception:
                    continue

                ifnames.append(ifname)

                if ifname not in CTProbeContainerCrawler.ifaces_monitored:
                    ok = self.start_netlink_collection(ifname,
                                                       peer.ip_addresses,
                                                       container_id,
                                                       **kwargs)
                    if ok:
                        CTProbeContainerCrawler.ifaces_monitored.append(ifname)
        except Exception as ex:
            logger.info("Error: %s" % str(ex))

        return ifnames

    def get_ifaddresses(self, ifname):
        """
          Get the list of IPv4 addresses on an interface name; in
          case none could be found yet, wait a bit and try again
        """

        for ctr in range(0, 4):
            res = []

            for data in netifaces.ifaddresses(ifname).get(2, []):
                addr = data.get('addr')
                if addr:
                    res.append(addr)
            if len(res):
                break
            time.sleep(0.01)

        return res

    def _crawl_in_system(self):
        for ifname in netifaces.interfaces():
            if ifname == 'lo':
                continue

            try:
                peer_ifindex = ethtool_get_peer_ifindex(ifname)
            except Exception:
                peer_ifindex = -1

            if peer_ifindex >= 0:
                yield PeerInterface(peer_ifindex,
                                    self.get_ifaddresses(ifname))
