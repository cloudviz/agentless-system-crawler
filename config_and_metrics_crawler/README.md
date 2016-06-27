Agentless System Crawler
========================

**Disclaimer:**
---------------

```
"The strategy is definitely: first make it work, then make it right, and, finally, make it fast."
```
The current state of this project is in the middle of "make it right".

**Prereq:**
-----------

 * Install Python 2.7.6
<<<<<<< HEAD
 * apt-get install python-dev # (for installing psutil)
=======
 * apt-get install python-dev (for installing psutil)
>>>>>>> cloudsight-crawler/master
 * apt-get install python-pip
 * pip install psutil
 * pip install netifaces
 * pip install bottle
<<<<<<< HEAD
 * pip install requests
 * pip install python-dateutil

=======
>>>>>>> cloudsight-crawler/master

**Quick test:**
---------------

```bash
% sudo python2.7 ./crawler/crawler.py
```

This should print something like this on stdout:

```
metadata	"metadata"	{"since_timestamp":1450194519.0,"features":"os,cpu","timestamp":"2015-12-16T20:27:25-0500","since":"BOOT","namespace":"192.168.1.3","system_type":"vm","compress":false}
os	"linux"	{"boottime":1450194519.0,"ipaddr":["127.0.0.1","192.168.1.3","192.168.122.1","192.168.123.1","172.17.42.1","9.80.80.71"],"osdistro":"Red Hat Enterprise Linux Workstation","osname":"Linux-2.6.32-573.8.1.el6.x86_64-x86_64-with-redhat-6.7-Santiago","osplatform":"x86_64","osrelease":"2.6.32-573.8.1.el6.x86_64","ostype":"linux","osversion":"#1 SMP Fri Sep 25 19:24:22 EDT 2015"}
cpu	"cpu-0"	{"cpu_idle":61.0,"cpu_nice":0.0,"cpu_user":19.5,"cpu_wait":0.0,"cpu_system":19.5,"cpu_interrupt":0.0,"cpu_steal":0.0,"cpu_used":39}
```

<<<<<<< HEAD
**Agentless, out-of-band Docker container crawling:**
----------------------------------------------

On the host machine, start an ubuntu Docker container that idles (Read docker
documents on how to install docker engine on the host machine). We define a
container as any process subtree with the `pid` namespace different to the
`init` process `pid` namespace

=======
**Agentless, out-of-band container crawling:**
----------------------------------------------

On host machine, start a ubuntu Docker container that idles (Read docker
documents on how to install docker engine on the host machine). We define
a container as any process subtree with the `pid` namespace different to the `init` process `pid` namespace

# @RICARDO let's try using a python maintained container instead of ubuntu... then we can delete half of this file! - pmeckif1
>>>>>>> cloudsight-crawler/master
```bash
% docker run -d ubuntu:latest bash -c "while true; do sleep 1; done"
```

Start crawler agent:

```bash
% cd agentless-crawler
% ./crawler.py --crawlmode OUTCONTAINER --url file:///tmp/test.csv --frequency 5
--features os,disk,process,connection,metric,package,file,config
--logfile /var/log/crawler.log --numprocesses 8
```

Wait 30 seconds for crawler agent to take a snapshot of the idle container, and
then make some changes in the ubuntu container (e.g., install vim):

```bash
% docker exec `docker ps -aq` apt-get install -y vim
```

<<<<<<< HEAD
Wait another 30 seconds for the crawler agent to take another snapshot of the
=======
Wait another 30 seconds for crawler agent to take another snapshot of the
>>>>>>> cloudsight-crawler/master
modified container. The snapshots will be stored in
/tmp/test.csv.[containerID].[number]. Find 2 snapshot files that was taken
before and after vim was installed. In this example, let's assume it is
/tmp/test.csv.9348177d4c8e.4 and /tmp/test.csv.9348177d4c8e.5. To clearly see
the differences between the snapshots, we first need to sort them:

```bash
% cd /tmp
% sort test.csv.9348177d4c8e.4 -k1,2 > test.csv.9348177d4c8e.4.sorted
% sort test.csv.9348177d4c8e.5 -k1,2 > test.csv.9348177d4c8e.5.sorted
```

Now using vimdiff, you can see the 2nd snapshot has a lot of new files added to
/usr/share/vim directory due to apt-get install vim

```bash
% vimdiff test.csv.9348177d4c8e.4.sorted test.csv.9348177d4c8e.5.sorted
```

**In-guest crawling:**
----------------------

We will start crawler agent in manual mode this time instead of periodic mode:

```bash
% sudo python2.7 crawler.py --url "file:///tmp/before.csv"  --features os,disk,process,package
```

<<<<<<< HEAD
Install emacs (or any other package):
=======
Install emacs:
>>>>>>> cloudsight-crawler/master

```bash
% apt-get install -y emacs
```

Use crawler to collect information again

```bash
% sudo python2.7 crawler.py --url "file:///tmp/after.csv" --features os,disk,process,package
```

Now we can find the differences before and after:

```bash
% diff /tmp/before.csv.0 /tmp/after.csv.0
```

You will probably see something similar to this below indicating package
emacs is now installed and disk space has shrunk due to installating emacs.

> > package       "emacs"
> > {"installed":null,"pkgname":"emacs","pkgsize":"25","pkgversion":"45.0ubuntu1"}


