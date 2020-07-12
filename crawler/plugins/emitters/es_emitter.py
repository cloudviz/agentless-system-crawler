from __future__ import print_function
import logging
from json import loads
from datetime import datetime
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

import traceback

from iemit_plugin import IEmitter

logger = logging.getLogger('crawlutils')


class ElasticEmitter(IEmitter):
    """
        Emitter to index the crawler frames into an elastic search index
    """

    def init(self, url, timeout=1, max_retries=5, emit_format='csv'):
        IEmitter.init(
            self,
            url,
            timeout=timeout,
            max_retries=max_retries,
            emit_format=emit_format
        )
        if emit_format == 'json':
            self.emit_per_line = True

        self.url = url
        self.elastic_index_name = self._get_elastic_index_name()
        self.elastic_engine = self._get_elasticsearch()

    def get_emitter_protocol(self):
        return "elastic"

    def _get_elasticsearch(self):
        """Returns an ElasticSearch Client

        Returns:
            Elasticsearch -- An ElasticSearch Client
        """
        url = "http{}".format(self.url[len(self.get_emitter_protocol()):])
        return Elasticsearch([url])

    def _get_elastic_index_name(self, prefix_identifier=None):
        """Returns the name of the elasticsearch index

        Keyword Arguments:
            prefix_identifier {str} -- Identifier prefix name for the elasticsearch index (default: {None})

        Returns:
            str -- Name of the Elasticsearch Index
        """

        if not prefix_identifier:
            prefix_identifier = 'deploy-bom'
        return "{}-{}".format(prefix_identifier, datetime.utcnow().strftime("%Y.%m.%d"))

    def emit(self, frame, compress=False, metadata={}, snapshot_num=0, **kwargs):
        """
            A wrapper function used by crawler to index the frame into an elasticsearch index
        """

        bulk_queue_size = 128

        try:
            frame_ = self.format(frame)

            if self.emit_per_line:
                frame_.seek(0)

            # Ignoring the redundant system metadata fields
            ignore_metadata_keys = ['uuid', 'features', 'namespace']

            for key in ignore_metadata_keys:
                metadata.pop(key)

            user_metadata_fields = [str(key) for key in metadata.keys()]

            self._bulk_insert_frame(
                frame=frame_,
                metadata_keys=user_metadata_fields,
                max_queue_size=bulk_queue_size
            )

        except Exception as error:
            traceback.print_exc()
            print(error)

    def __add_metadata(self, metadata=None, user_metadata_keys=None, json_document=None):
        """Adds user specified metadata_keys to each json_document

        Keyword Arguments:
            metadata {dict} -- Metadata from crawler and user (default: {None})
            user_metadata_keys {list} -- List of custom user metadata fields (default: {None})
            json_document {dict} -- JSON Formatted Document (default: {None})
        """
        if not isinstance(metadata, dict):
            raise TypeError("'metadata' should be of {}".format(dict))

        if not isinstance(user_metadata_keys, list):
            raise TypeError("'metadata_keys' should be of {}".format(list))

        if not isinstance(json_document, dict):
            raise TypeError("'elastic_doc' should be of {}".format(dict))

        for key in user_metadata_keys:
            json_document[key] = metadata.get(key, None)

        return json_document

    def __gen_elastic_document(self, source_field_body=None):
        """Formats source_field_body into an elastic document

        Keyword Arguments:
            source_field_body {dict} -- Crawler Frame (default: {None})
        """

        if not isinstance(source_field_body, dict):
            raise TypeError("'source_field_body' should be {}".format(dict))

        _elastic_document = {
            "_index": self.elastic_index_name,
            "_type": "doc",
            "_source": source_field_body
        }

        return _elastic_document

    def _gen_elastic_documents(self, frame=None, metadata_keys=None):
        """Helper function to add metadata_keys to each doc in the frame and format them into an elastic document

        Keyword Arguments:
            frame {StringO} -- Crawler Frame (default: {None})
            metadata_keys {list} -- List of custom user metadata fields (default: {None})
        """

        if not isinstance(metadata_keys, list):
            raise TypeError("'metadata_keys' should be of {}".format(list))

        try:
            # This metadata contains both crawler and user specified metadata fields
            system_metadata = loads(frame.readline())

            for doc in frame:
                formatted_json_document = loads(doc.strip())
                _formatted_doc = self.__add_metadata(
                    metadata=system_metadata,
                    user_metadata_keys=metadata_keys,
                    json_document=formatted_json_document
                )
                elastic_document = self.__gen_elastic_document(_formatted_doc)
                yield elastic_document

        except ValueError as value_error:
            print("Invalid JSON Formatting in frame")
            print(value_error)

    def _bulk_insert_frame(self, frame=None, metadata_keys=None, max_queue_size=64):
        """Bulk insert the crawler frame into the elasticsearch index

        Keyword Arguments:
            frame {cStringIO} -- Crawler Frame (default: {None})
            metadata_keys {list} -- List of custom user metadata fields (default: {None})
            max_queue_size {int} -- Maximum number of documents to queue
                                    before performing a bulk insert (default: {64})
        """

        if not isinstance(metadata_keys, list):
            raise TypeError("'metadata_keys' should be of {}".format(list))

        if not isinstance(max_queue_size, int):
            raise TypeError("'max_queue_size' should be of {}".format(int))

        bulk_queue = []
        queue_size = 0

        elastic_documents = self._gen_elastic_documents(
            frame=frame,
            metadata_keys=metadata_keys
        )

        for document in elastic_documents:
            # print(document)
            bulk_queue.append(document)
            queue_size = (queue_size + 1) % max_queue_size

            if queue_size == 0:
                bulk(
                    self.elastic_engine,
                    bulk_queue,
                    request_timeout=30,
                    max_retries=5
                )
                del bulk_queue[:]  # Empty the queue

        # NOTE: The number of documents in the frame might not always be divisible by max_queue_size
        # Indexing any left over documents in the bulk_queue
        if bulk_queue:
            bulk(
                self.elastic_engine,
                bulk_queue,
                request_timeout=30,
                max_retries=5
            )
