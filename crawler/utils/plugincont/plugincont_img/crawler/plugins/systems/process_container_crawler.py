import logging

import psutil

from icrawl_plugin import IContainerCrawler
from utils.features import ProcessFeature

logger = logging.getLogger('crawlutils')


class ProcessContainerCrawler(IContainerCrawler):

    def get_feature(self):
        return 'process'

    def crawl(self, container_id, avoid_setns=False, **kwargs):
        if avoid_setns:
            raise NotImplementedError()
        return self._crawl_in_system()

    def _crawl_in_system(self):
        created_since = -1
        for p in psutil.process_iter():
            create_time = (
                p.create_time() if hasattr(
                    p.create_time,
                    '__call__') else p.create_time)
            if create_time <= created_since:
                continue
            yield self._crawl_single_process(p)

    def _crawl_single_process(self, p):
        """Returns a ProcessFeature"""
        create_time = (
            p.create_time() if hasattr(
                p.create_time,
                '__call__') else p.create_time)

        name = (p.name() if hasattr(p.name, '__call__'
                                    ) else p.name)
        cmdline = (p.cmdline() if hasattr(p.cmdline, '__call__'
                                          ) else p.cmdline)
        pid = (p.pid() if hasattr(p.pid, '__call__') else p.pid)
        status = (p.status() if hasattr(p.status, '__call__'
                                        ) else p.status)
        if status == psutil.STATUS_ZOMBIE:
            cwd = 'unknown'  # invalid
        else:
            try:
                cwd = (p.cwd() if hasattr(p, 'cwd') and
                       hasattr(p.cwd, '__call__') else p.getcwd())
            except Exception:
                logger.error('Error crawling process %s for cwd'
                             % pid, exc_info=True)
                cwd = 'unknown'
        ppid = (p.ppid() if hasattr(p.ppid, '__call__'
                                    ) else p.ppid)
        try:
            if (hasattr(p, 'num_threads') and
                    hasattr(p.num_threads, '__call__')):
                num_threads = p.num_threads()
            else:
                num_threads = p.get_num_threads()
        except:
            num_threads = 'unknown'

        try:
            username = (p.username() if hasattr(p, 'username') and
                        hasattr(p.username, '__call__') else
                        p.username)
        except:
            username = 'unknown'

        if username == 'nobody':
            return

        openfiles = []
        try:
            for f in p.get_open_files():
                openfiles.append(f.path)
            openfiles.sort()
        except psutil.AccessDenied:
            print "got psutil.AccessDenied"
            openfiles = []

        feature_key = '{0}/{1}'.format(name, pid)
        return (feature_key, ProcessFeature(
            str(' '.join(cmdline)),
            create_time,
            cwd,
            name,
            openfiles,
            pid,
            ppid,
            num_threads,
            username,
        ), 'process')
