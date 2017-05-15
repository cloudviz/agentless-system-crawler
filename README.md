Agentless System Crawler 
[![Build Status](https://travis-ci.org/cloudviz/agentless-system-crawler.svg?branch=master)](https://travis-ci.org/cloudviz/agentless-system-crawler)
[![Code Coverage](https://codecov.io/gh/cloudviz/agentless-system-crawler/branch/master/graph/badge.svg)](https://codecov.io/gh/cloudviz/agentless-system-crawler)
========================

**Disclaimer:**
---------------

```
"The strategy is definitely: first make it work, then make it right, and, finally, make it fast."
```
The current state of this project is in the middle of "make it right".

**Prereqs and Building:**
-----------
To run the crawler you'll need to do the following steps in the environment
in which you want it to run:

 * Install Python 2.7.5
 * apt-get install python-dev
 * apt-get install python-pip
 * pip install psutil
 * pip install netifaces
 * pip install requests
 * pip install python-dateutil

If you want to run the crawler in a container then build the `crawler` image
using the provided `Dockerfile`:

`sudo docker build -t crawler .`

or run:

`sudo make build`

To run the test cases, run:

`sudo make test`

**Running the Crawler:**
------------------------
To run the crawler natively on the Docker host system, use:
```
sudo python crawler/crawler.py ...
```

To run the crawler in a container use:
```
sudo docker run \
    --privileged \
    --net=host \
    --pid=host \
    -v /cgroup:/cgroup:ro \
    -v /sys/fs/cgroup:/sys/fs/cgroup:ro \
    -v /var/lib/docker:/var/lib/docker:ro \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v $PWD/output:/crawler/output \
    -it crawler ...
```

Note: this assumes a directory called `output` is present to store the output
of the crawler scans, so you may need to create (`mkdir output`) first.

The following examples will use `CRAWLER` as a short-hand notation to mean
one of the above commands.

***Quick tests:***
-----------------

`$ CRAWLER --help`
Should show the help text.

`$ CRAWLER`

Should print something like this on stdout:

```
metadata "metadata" {"since_timestamp":1450194519.0,"features":"os,cpu","timestamp":"2015-12-16T20:27:25-0500","since":"BOOT","namespace":"192.168.1.3","system_type":"vm","compress":false}
os "linux" {"boottime":1450194519.0,"ipaddr":["127.0.0.1","192.168.1.3","192.168.122.1","192.168.123.1","172.17.42.1","9.80.80.71"],"osdistro":"Red Hat Enterprise Linux Workstation","osname":"Linux-2.6.32-573.8.1.el6.x86_64-x86_64-with-redhat-6.7-Santiago","osplatform":"x86_64","osrelease":"2.6.32-573.8.1.el6.x86_64","ostype":"linux","osversion":"#1 SMP Fri Sep 25 19:24:22 EDT 2015"}
cpu "cpu-0" {"cpu_idle":61.0,"cpu_nice":0.0,"cpu_user":19.5,"cpu_wait":0.0,"cpu_system":19.5,"cpu_interrupt":0.0,"cpu_steal":0.0,"cpu_used":39}
```

**Crawling Containers:**
-------------------------------
To crawl all containers running on the host use the following command:
```
$ CRAWLER --crawlmode OUTCONTAINER \
          --url file://output/test.csv \
          --features os,disk,process,connection,metric,package,file,config \
          --logfile output/crawler.log
```

This will take a snapshot of the existing containers and put the results in
a file called `output/test.csv.[containerID].[number]`.

**Continuous Container Crawling:**
-----------------------------------------
To crawl all containers running on the host use the following command:
```
$ CRAWLER --crawlmode OUTCONTAINER \
          --url file://output/test.csv \
          --frequency 5 \
          --features os,disk,process,connection,metric,package,file,config \
          --logfile output/crawler.log \
          --numprocesses 8
```

To test this, start a container:
```
sudo docker run -d --name=test ubuntu bash -c "while true; do sleep 1; done"
```

Wait 30 seconds for a snapshot to be taken, then run a secondary command in
the container to force some changes:
```
sudo docker exec test apt-get install -y vim
```

Wait another 30 seconds for the crawler agent to take another snapshot of the
modified container. The snapshots will be stored in
output/test.csv.[containerID].[number]. Find 2 snapshot files that was taken
before and after vim was installed. In this example, let's assume it is
test.csv.9348177d4c8e.4 and test.csv.9348177d4c8e.5. To clearly see
the differences between the snapshots, we first need to sort them:

```bash
$ cd output
$ sort test.csv.9348177d4c8e.4 -k1,2 > test.csv.9348177d4c8e.4.sorted
$ sort test.csv.9348177d4c8e.5 -k1,2 > test.csv.9348177d4c8e.5.sorted
```

Now using vimdiff, you can see the 2nd snapshot has a lot of new files added to
/usr/share/vim directory due to apt-get install vim

```bash
$ vimdiff test.csv.9348177d4c8e.4.sorted test.csv.9348177d4c8e.5.sorted
```

Finally, delete the test container:
```
sudo docker rm -f test
```

**In-guest crawling:**
----------------------
We will start crawler agent in manual mode this time instead of periodic mode:

```bash
$ CRAWLER --url "file://output/before.csv"  --features os,disk,process,package
```

Install emacs (or any other package):

```bash
$ apt-get install -y emacs
```

Use crawler to collect information again

```bash
$  CRAWLER --url "file://output/after.csv" --features os,disk,process,package
```

Now we can find the differences before and after:

```bash
$ diff output/before.csv.0 output/after.csv.0
```

You will probably see something similar to this below indicating package
emacs is now installed and disk space has shrunk due to installating emacs.

> > package       "emacs"
> > {"installed":null,"pkgname":"emacs","pkgsize":"25","pkgversion":"45.0ubuntu1"}
