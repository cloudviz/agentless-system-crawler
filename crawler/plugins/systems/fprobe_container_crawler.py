
import errno
import glob
import json
import logging
import netifaces
import os
import psutil
import pwd
import signal
import time
import utils.dockerutils

from collections import namedtuple
from icrawl_plugin import IContainerCrawler
from utils.ethtool import ethtool_get_peer_ifindex
from utils.misc import get_uint_arg
from utils.namespace import run_as_another_namespace
from utils.process_utils import start_child
from utils.socket_utils import open_udp_port, if_indextoname

logger = logging.getLogger('crawlutils')

PeerInterface = namedtuple('PeerInterface', ['peer_ifindex', 'ip_addresses'])
NetflowFeature = namedtuple('NetflowFeature', ['data'])


class FprobeContainerCrawler(IContainerCrawler):

    BIND_ADDRESS = '127.0.0.1'

    # Interface where fprobes were started on.
    fprobes_started = set()

    # Since we don't get notified when a container dies
    # we need to periodically check the interfaces on the host
    # against those in fprobes_started.
    next_cleanup = 0

    def get_feature(self):
        return 'fprobe'

    @staticmethod
    def interfaces_with_fprobes():
        """
          Get a set of interfaces for which fprobe is already running
          We walk the list of processes and check the 'fprobe' ones
          and determine the parameter passed after '-i', which is the
          name of the interface. We only recognize those with target
          address for the collector being 127.0.0.1.
        """
        res = []

        for proc in psutil.process_iter():
            if proc.name() == 'fprobe':
                params = proc.cmdline()
                targetaddress = params[-1].split(':')[0]
                if targetaddress == FprobeContainerCrawler.BIND_ADDRESS:
                    try:
                        i = params.index('-i')
                        logger.debug('fprobe running on iface %s' %
                                     params[i+1])
                        res.append(params[i + 1])
                    except:
                        pass

        return set(res)

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

    def start_fprobe(self, ifname, user, bindaddr, port, **kwargs):
        """
          Start the fprobe process on the given interface, using the
          given user, and use the bindaddr and port as the collector.
          This function returns the process ID of the started process
          and an errcode (errno) in case an error was encountered in
          the start_child function.
        """
        lifetime_timeout = get_uint_arg('lifetime_timeout', 30, **kwargs)
        idle_timeout = get_uint_arg('idle_timeout', 30, **kwargs)
        netflow_version = get_uint_arg('netflow_version', 5, **kwargs)
        if netflow_version not in [1, 5, 7]:
            logger.info('Unsupported netflow version was chosen: %d' %
                        netflow_version)
            netflow_version = 5

        terminate_process = kwargs.get('terminate_fprobe', 'FALSE').upper()
        setsid = terminate_process in ['0', 'FALSE']

        params = ['fprobe',
                  '-i', ifname,
                  '-u', user,
                  '-n', '%d' % netflow_version,
                  '-fip',
                  '-l', '2',
                  '-e', '%d' % lifetime_timeout,
                  '-d', '%d' % idle_timeout,
                  '%s:%d' % (bindaddr, port)]
        try:
            pid, errcode = start_child(params, [], [0, 1, 2],
                                       [signal.SIGCHLD],
                                       setsid=setsid)
            logger.info('Started fprobe as pid %d' % pid)
        except:
            pid = -1
            errcode = errno.EINVAL

        return pid, errcode

    def start_collector(self, user, socket, output_dir, watch_pid, metadata,
                        **kwargs):
        """
          Start the collector process; have it drop privileges by
          switching to the given user; have it write the data to the
          output_dir and use a filename pattern given by
          filenamepattern; have it watch the process with the given
          watch_pid
        """
        filepattern = kwargs.get('output_filepattern',
                                 'fprobe-{ifname}-{timestamp}')

        params = ['socket-datacollector',
                  '--user', user,
                  '--sockfd', str(socket.fileno()),
                  '--dir', output_dir,
                  '--filepattern', filepattern,
                  '--watch-pid', str(watch_pid),
                  '--metadata', json.dumps(metadata),
                  '--md-filter', 'ip-addresses']
        try:
            pid, errcode = start_child(params, [socket.fileno()], [],
                                       [signal.SIGCHLD],
                                       setsid=True)
            logger.info('Started collector as pid %d' % pid)
        except:
            pid = -1
            errcode = errno.EINVAL

        return pid, errcode

    def start_netflow_collection(self, ifname, ip_addresses, container_id,
                                 **kwargs):
        """
          Start the collector and the fprobe. Return false in case of an
          error.

          Note: Fprobe will terminate when the container ends. The collector
                watches the fprobe via its PID and will terminate once fprobe
                is gone. To enable this, we have to start the collector
                after fprobe. Since this is relatively quick, we won't miss
                any netflow packets in the collector.
        """

        fprobe_user = kwargs.get('fprobe_user', 'nobody')
        try:
            passwd = pwd.getpwnam(fprobe_user)
        except Exception as ex:
            logger.error('Could not find user %s on this system: %s' %
                         (fprobe_user, str(ex)))
            return False

        fprobe_output_dir = kwargs.get('fprobe_output_dir',
                                       '/tmp/crawler-fprobe')
        if not self.setup_outputdir(fprobe_output_dir, passwd.pw_uid,
                                    passwd.pw_gid):
            return False

        # Find an open port; we pass the port number for fprobe and the
        # file descriptor of the listening socket to the collector
        bindaddr = FprobeContainerCrawler.BIND_ADDRESS
        sock, port = open_udp_port(bindaddr, 40000, 65535)
        if not sock:
            return False

        fprobe_pid, errcode = self.start_fprobe(ifname, fprobe_user,
                                                bindaddr, port,
                                                **kwargs)

        if fprobe_pid < 0:
            logger.error('Could not start fprobe: %s' % os.strerror(errcode))
            sock.close()
            return False

        metadata = {
            'ifname': ifname,
            'ip-addresses': ip_addresses,
        }

        collector_pid, errcode = self.start_collector(fprobe_user, sock,
                                                      fprobe_output_dir,
                                                      fprobe_pid,
                                                      metadata,
                                                      **kwargs)

        sock.close()

        if collector_pid == -1:
            logger.error('Could not start collector: %s' %
                         os.strerror(errcode))
            os.kill(fprobe_pid, signal.SIGKILL)
            return False

        return True

    def cleanup(self, **kwargs):
        """
          Check the available interfaces on the host versus those ones we
          have fprobes running and remove those where the interface has
          disappeared. We clean up the files with netflow data that were
          written for those interfaces.
        """
        devices = netifaces.interfaces()

        for ifname in FprobeContainerCrawler.fprobes_started.copy():
            if ifname not in devices:
                FprobeContainerCrawler.fprobes_started.remove(ifname)
                self.remove_datafiles(ifname, **kwargs)

    def crawl(self, container_id, avoid_setns=False, **kwargs):
        """
          Start fprobe + data collector pairs on the interfaces of
          the given container; collect the files that the collector
          wrote and return their content.
        """
        if time.time() > FprobeContainerCrawler.next_cleanup:
            self.cleanup(**kwargs)
            FprobeContainerCrawler.next_cleanup = time.time() + 30

        ifnames = self.start_container_fprobes(container_id, avoid_setns,
                                               **kwargs)

        return self.collect_files(container_id, ifnames, **kwargs)

    def create_filenamepattern(self, **kwargs):
        """
          Create the filename pattern for the files where the
          socket-datacollector writes its data into.
        """
        output_dir = kwargs.get('fprobe_output_dir', '/tmp/crawler-fprobe')
        filepattern = kwargs.get('output_filepattern',
                                 'fprobe-{ifname}-{timestamp}')
        filenamepattern = os.path.join(output_dir, filepattern)

        return filenamepattern.format(**kwargs)

    def remove_datafiles(self, ifname, **kwargs):
        """
          Remove netflow data files that belong to an interface
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
            except:
                pass

    def collect_files(self, container_id, ifnames, **kwargs):
        """
          Collect the files with netflow data for the given interface
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
                    logger.info('Error reading datafile: %s' % str(ex))
                    continue

                try:
                    os.remove(filename)
                except Exception as ex:
                    logger.info('Error removing datafile: %s' % str(ex))
                    continue

                feature_key = '{0}-{1}'.format('fprobe', ifname)

                yield (feature_key, NetflowFeature(
                    data
                ), 'fprobe')

    def start_container_fprobes(self, container_id, avoid_setns=False,
                                **kwargs):
        """
          Unless fprobes are already running on the interfaces of the
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
            for peer in peers:
                try:
                    ifname = if_indextoname(peer.peer_ifindex)
                except:
                    continue

                ifnames.append(ifname)

                if ifname not in FprobeContainerCrawler.fprobes_started:
                    FprobeContainerCrawler.fprobes_started.add(ifname)
                    logger.info('Need to start fprobe on %s' % ifname)
                    self.start_netflow_collection(ifname,
                                                  peer.ip_addresses,
                                                  container_id,
                                                  **kwargs)
        except Exception as ex:
            logger.info("Error: %s" % str(ex))

        return ifnames

    def get_ifaddresses(self, ifname):
        """
          Get the list of IPv4 addresses on an interface name
        """
        return [a.get('addr')
                for a in netifaces.ifaddresses(ifname).get(2, [])]

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


FprobeContainerCrawler.fprobes_started = \
    FprobeContainerCrawler.interfaces_with_fprobes()
