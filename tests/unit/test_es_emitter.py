import sys
sys.path.append('crawler')

from unittest import TestCase, main
from plugins.emitters.es_emitter import ElasticEmitter
from base_crawler import BaseFrame


class TestElasticEmitter(TestCase):

    def setUp(self):
        # {"system_type": "host", "field2": "abc",
        # "timestamp": "2020-07-11T12:52:12-0500", "field1": 123,
        # "namespace": "192.168.1.221",
        # "uuid": "41a261d1-6dbd-4e0c-b8ed-68388e73df11",
        # "features": "os,disk,process,package"}
        self.frame = BaseFrame(feature_types=["os", "disk",
                                              "process", "package"])
        self.frame.metadata['namespace'] = '192.168.1.221'
        self.system_type = "host"
        self.frame.metadata['system_type'] = self.system_type

        self.extra_metadata = {"field1": 123, "field2": "abc"}
        self.frame.metadata.update(self.extra_metadata)

        self.frame.add_features([
            (
                                "os",
                                {"boottime": 1594481866.0,
                                 "uptime": 8066.0,
                                 "ipaddr": ["127.0.0.1", "192.168.1.221"],
                                 "os": "ubuntu",
                                 "os_version": "18.04",
                                 "os_kernel": "Linux-4.15.0-109-generic-x86_64-with-Ubuntu-18.04-bionic",
                                 "architecture": "x86_64"},
                                "os"
                                ),
                                (
                                    "disk",
                                    {"partitionname": "proc",
                                    "freepct": 100.0,
                                    "fstype": "proc",
                                    "mountpt": "/proc",
                                    "mountopts": "rw,nosuid,nodev,noexec,relatime",
                                    "partitionsize": 0
                                    },
                                    "disk"
                                ),
                                (
                                    "process",
                                    {"cmd": "/usr/lib/postgresql/10/bin/postgres -D /var/lib/postgresql/10/main -c config_file=/etc/postgresql/10/main/postgresql.conf",
                                    "created": 1594481947.07,
                                    "cwd": "/var/lib/postgresql/10/main",
                                    "pname": "postgres",
                                    "openfiles": ["/var/log/postgresql/postgresql-10-main.log",
                                                "/var/log/postgresql/postgresql-10-main.log",
                                                "/var/log/postgresql/postgresql-10-main.log",
                                                "/var/log/postgresql/postgresql-10-main.log"],
                                    "mmapfiles": [], "pid": 1831, "ppid": 1,
                                    "threads": 1,
                                    "user": "postgres"},
                                    "process"
                                ),
                                (
                                    "package",
                                    {"installed": None,
                                    "pkgname": "postgresql-10",
                                    "pkgsize": "14816",
                                    "pkgversion": "10.12-0ubuntu0.18.04.1",
                                    "pkgarchitecture": "amd64"},
                                    "package"
                                )
                            ])

        self.emitter = ElasticEmitter()
        self.emitter.init(
            url="elastic://localhost:9200",
            emit_format='json'
        )

    def test_gen_elastic_documents(self):
        frame = self.emitter.format(self.frame)

        all_metadata_keys = self.frame.metadata.keys()

        es_metadata_keys = []
        existing_keys_in_each_frame = {"uuid", "features", "namespace"}

        for key in all_metadata_keys:
            if key not in existing_keys_in_each_frame:
                es_metadata_keys.append(key)

        if self.emitter.emit_per_line:
            frame.seek(0)

        elastic_docs = self.emitter._gen_elastic_documents(
            frame, es_metadata_keys)
        for es_doc, doc in zip(elastic_docs, self.frame.data):
            doc[1]['system_type'] = self.system_type
            doc[1]['timestamp'] = self.frame.metadata['timestamp']
            for key, value in self.extra_metadata.items():
                doc[1][key] = value
            self.assertEqual(es_doc['_source'], doc[1])

    def tearDown(self):
        del self.frame
        del self.emitter


if __name__ == '__main__':
    main()
