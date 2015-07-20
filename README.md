
**Prereq:**
	* Install Python 2.7.6
	* apt-get install python-dev (for installing psutil)
	* apt-get install python-pip
	* pip install simplejson
	* pip install psutil
	* pip install netifaces
	* pip install bottle

**Agentless, out-of-band container crawling:**

	On host machine, start a ubuntu container that idles (Read docker documents on
	how to install docker engine on the host machine)

	% docker run -d ubuntu:latest bash -c "while true; do sleep 1; done"

	Start crawler agent:

	% cd agentless-crawler
	% ./crawler.py --crawlmode OUTCONTAINER --crawlContainers ALL --url
	file:///tmp/test.csv --since EPOCH --frequency 5 --features
	os,disk,process,connection,metric,package,file,config --compress false
	--logfile /var/log/crawler.log --numprocesses 8 --linkContainerLogFiles

	Wait 30 seconds for crawler agent to take a snapshot of the idle container, and
	then make some changes in the ubuntu container (e.g., install vim):

	% docker exec `docker ps -aq` apt-get install -y vim

	Wait another 30 seconds for crawler agent to take another snapshot of the
	modified container. The snapshots will be stored in
	/tmp/test.csv.[containerID].[number]. Find 2 snapshot files that was taken
	before and after vim was installed. In this example, let's assume it is
	/tmp/test.csv.9348177d4c8e.4 and /tmp/test.csv.9348177d4c8e.5. To clearly see
	the differences between the snapshots, we first need to sort them:

	% cd /tmp
	% sort test.csv.9348177d4c8e.4 -k1,2 > test.csv.9348177d4c8e.4.sorted
	% sort test.csv.9348177d4c8e.5 -k1,2 > test.csv.9348177d4c8e.5.sorted

	Now using vimdiff, you can see the 2nd snapshot has a lot of new files added to
	/usr/share/vim directory due to apt-get install vim

	% vimdiff test.csv.9348177d4c8e.4.sorted test.csv.9348177d4c8e.5.sorted

**In-guest crawling:**

	We will start crawler agent in manual mode this time instead of periodic mode:

	% ./crawler.py --url "file:///tmp/before.csv" --since EPOCH --features
	os,disk,process,package --compress false

	Install emacs:

	% apt-get install -y emacs

	Use crawler to collect information again

	% ./crawler.py --url "file:///tmp/after.csv" --since EPOCH --features
	os,disk,process,package --compress false

	Now we can find the differences before and after:

	% diff /tmp/before.csv.0 /tmp/after.csv.0

	You will probably see something similar to this below indicating package
	emacs is now installed and disk space has shrunk due to installating emacs.

	< disk  "/"
	{"partitionname":"/dev/xvda2","freepct":97.7,"fstype":"ext3","mountpt":"/","mountopts":"rw,noatime,errors=remount-ro,barrier=0","partitionsize":105300402176}
	---
	> disk  "/"
	> {"partitionname":"/dev/xvda2","freepct":97.6,"fstype":"ext3","mountpt":"/","mountopts":"rw,noatime,errors=remount-ro,barrier=0","partitionsize":105300402176}
	67a68
	> package       "emacs"
	> {"installed":null,"pkgname":"emacs","pkgsize":"25","pkgversion":"45.0ubuntu1"}


