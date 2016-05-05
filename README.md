Crawlers
========
This repository houses config & metrics crawlers and logcrawlers code which is packaged for three purposes:

Crawlers for Alchemy Containers Kraken Hosts
--------------------------------------------
<pre>packaging/create_alchemy_crawler_package.sh <environmenrt(eg: prod-dal09)></pre>
This is a package that is pushed into the kraken deb repository to deploy config & metrics crawlers and logcrawlers on containers hosts.

Registry Crawlers
-----------------
<pre>packaging/create_registry_crawler_package.sh</pre>
This is a package used to deploy the regcrawler on VA infrastructure.

VA Config & Metrics Crawlers
----------------------------
<pre>
cd config_and_metrics_crawlers
docker build
</pre>
This is a container that runs the config & metrics crawler on VA infrastructure.

Tests
-----
<pre>
pip install -r tests/functional/requirements.txt
py.test tests/functional
</pre>
This runs functional tests.

There are also a lot of shell based tests in tests/ which need to be run as root, will leave files in /tmp and /root, will leave crawlers running on your machine and might delete all of your files.
