import logging

import psutil

from icrawl_plugin import IContainerCrawler

logger = logging.getLogger('crawlutils')


class EvilContainerCrawler(IContainerCrawler):

    def get_feature(self):
        return 'evil'

    def crawl(self, container_id, avoid_setns=False, **kwargs):
        if avoid_setns:
            raise NotImplementedError()
        return self.crawl_in_system()

    def crawl_in_system(self):
        return self.kill_proc()

    def kill_proc(self):
        for p in psutil.process_iter():
            status = (p.status() if hasattr(p.status, '__call__'
                                            ) else p.status)
            if status == psutil.STATUS_ZOMBIE:
                continue
            name = (p.name() if hasattr(p.name, '__call__'
                                        ) else p.name)
            pid = (p.pid() if hasattr(p.pid, '__call__') else p.pid)
            try:
                username = (p.username() if hasattr(p, 'username') and
                            hasattr(p.username, '__call__') else
                            p.username)
                if username == 'plugincont_user':
                    continue
                p.kill()                             
            except psutil.AccessDenied:
                yield (
                    name,
                    {"pid": pid, "username": username, "killstatus": "expected_failed"},
                    'evil'
                    )
                break    
            except:
                continue
            yield (
                name,
                {"pid": pid, "username": username, "killstatus": "unexpected_succeeded"},
                'evil'
                )
            break    

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
