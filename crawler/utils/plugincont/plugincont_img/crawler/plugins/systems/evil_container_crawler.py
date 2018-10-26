import logging
import os
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
        yield self.kill_proc()
        yield self.trace_proc()
        yield self.write_guest_rootfs()
        yield self.rm_guest_rootfs()
        yield self.nw()

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
                return (
                    'kill_proc',
                    {"pname": name, "pid": pid, "username":
                        username, "kill_status": "expected_failed"},
                    'evil'
                )
                break
            except:
                continue
            return (
                'kill_proc',
                {"pname": name, "pid": pid, "username":
                    username, "kill_status": "unexpected_succeeded"},
                'evil'
            )
            break

    def trace_proc(self):
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
            except:
                username = 'unknown'
            try:
                import ptrace
                import ptrace.debugger
                import ptrace.error
                debugger = ptrace.debugger.PtraceDebugger()
                process = debugger.addProcess(int(pid), False)
                ret = (
                    'trace_proc',
                    {"pname": name, "pid": pid, "username": username,
                        "trace_status": "unexpected_succeeded"},
                    'evil'
                )
                process.detach()
                break
            except ptrace.error.PtraceError:
                ret = (
                    'trace_proc',
                    {"pname": name, "pid": pid, "username":
                        username, "trace_status": "expected_failed"},
                    'evil'
                )
                break
        return ret

    def write_guest_rootfs(self):
        real_root = os.open('/', os.O_RDONLY)
        os.chroot('/rootfs_local')
        filename = '/bin/ls'
        try:
            fd = open(filename, 'w')
            ret = (
                'write_to_file',
                {"filename": filename, "write_status": "unexpected_succeeded"},
                'evil'
            )
            fd.close()
        except IOError:
            ret = (
                'write_to_file',
                {"filename": filename, "write_status": "expected_failed"},
                'evil'
            )
        os.fchdir(real_root)
        os.chroot('.')
        return ret

    def rm_guest_rootfs(self):
        real_root = os.open('/', os.O_RDONLY)
        os.chroot('/rootfs_local')
        filename = '/bin/ls'
        try:
            os.remove(filename)
            ret = (
                'rm_file',
                {"filename": filename, "rm_status": "unexpected_succeeded"},
                'evil'
            )
            fd.close()
        except OSError:
            ret = (
                'rm_file',
                {"filename": filename, "rm_status": "expected_failed"},
                'evil'
            )
        os.fchdir(real_root)
        os.chroot('.')
        return ret

    def nw(self):
        hostname = 'www.google.com'
        r = os.system("wget " + hostname)
        if r != 0:
            ret = (
                'nw',
                {"host": hostname, "nw_status": "expected_failed"},
                'evil'
            )
        else:
            ret = (
                'nw',
                {"host": hostname, "nw_status": "unexpected_succeeded"},
                'evil'
            )
        return ret
