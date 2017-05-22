import logging
import os
import json
import time

import requests

from iemit_plugin import IEmitter
from plugins.emitters.base_http_emitter import BaseHttpEmitter
from utils.crawler_exceptions import EmitterUnsupportedFormat

logger = logging.getLogger('crawlutils')


class SasEmitter(BaseHttpEmitter, IEmitter):

    def get_emitter_protocol(self):
        return 'sas'

    def init(self, url, timeout=1, max_retries=5, emit_format='csv'):
        IEmitter.init(self, url,
                      timeout=timeout,
                      max_retries=max_retries,
                      emit_format=emit_format)
        if emit_format != 'csv':
            raise EmitterUnsupportedFormat('Not supported: %s' % emit_format)

    def emit(self, frame, compress=False,
             metadata={}, snapshot_num=0, **kwargs):
        """

        :param frame: a frame containing extracted features
        :param compress:
        :param metadata:
        :param snapshot_num:
        :return: None
        """
        self.token_filepath = kwargs.get("token_filepath", "")
        self.access_group_filepath = kwargs.get("access_group_filepath", "")
        self.cloudoe_filepath = kwargs.get("cloudoe_filepath", "")
        self.ssl_verification = kwargs.get("ssl_verification", "")

        iostream = self.format(frame)
        if compress:
            proto = self.get_emitter_protocol()
            raise NotImplementedError(
                '%s emitter does not support gzip.' % proto
            )
        if self.emit_per_line:
            iostream.seek(0)
            for line in iostream.readlines():
                self.post(line, metadata)
        else:
            self.post(iostream.getvalue(), metadata)

    '''
    This function retrievs sas token information from k8s secrets.
    Current model of secret deployment in k8s is through mounting
    'secret' inside crawler container.
    '''
    def get_sas_tokens(self):
        assert(os.path.exists(self.token_filepath))
        assert(os.path.exists(self.access_group_filepath))
        assert(os.path.exists(self.cloudoe_filepath))

        fp = open(self.access_group_filepath)
        access_group = fp.read().rstrip('\n')
        fp.close()

        fp = open(self.cloudoe_filepath)
        cloudoe = fp.read().rstrip('\n')
        fp.close()

        fp = open(self.token_filepath)
        token = fp.read().rstrip('\n')
        fp.close()

        return(token, cloudoe, access_group)

    '''
    SAS requires following crawl metadata about entity
    being crawled.
        - timestamp
        - namespace
        - features
        - source type
    This function parses the crawled metadata feature and
    gets these information.
    '''
    def __parse_crawl_metadata(self, content=''):
        metadata_str = content.split('\n')[0].split()[2]
        metadata_json = json.loads(metadata_str)
        timestamp = metadata_json.get('timestamp', '')
        namespace = metadata_json.get('namespace', '')
        features = metadata_json.get('features', '')
        system_type = metadata_json.get('system_type', '')

        return (namespace, timestamp, features, system_type)

    def post(self, content='', metadata={}):
        (namespace, timestamp, features, system_type) =\
            self.__parse_crawl_metadata(content)
        (token, cloudoe, access_group) = self.get_sas_tokens()
        headers = {'content-type': 'application/csv'}
        headers.update({'Cloud-OE-ID': cloudoe})
        headers.update({'X-Auth-Token': token})

        params = {}
        params.update({'access_group': access_group})
        params.update({'namespace': namespace})
        params.update({'features': features})
        params.update({'timestamp': timestamp})
        params.update({'source_type': system_type})

        self.url = self.url.replace('sas:', 'https:')

        verify = True
        if self.ssl_verification == "False":
            verify = False

        for attempt in range(self.max_retries):
            try:
                response = requests.post(self.url, headers=headers,
                                         params=params,
                                         data=content, verify=verify)
            except requests.exceptions.ChunkedEncodingError as e:
                logger.exception(e)
                logger.error(
                    "POST to %s resulted in exception (attempt %d of %d), "
                    "Exiting." % (self.url, attempt + 1, self.max_retries))
                break
            except requests.exceptions.RequestException as e:
                logger.exception(e)
                logger.error(
                    "POST to %s resulted in exception (attempt %d of %d)" %
                    (self.url, attempt + 1, self.max_retries))
                time.sleep(2.0 ** attempt * 0.1)
                continue
            if response.status_code != requests.codes.ok:
                logger.error("POST to %s resulted in status code %s: %s "
                             "(attempt %d of %d)" %
                             (self.url, str(response.status_code),
                              response.text, attempt + 1, self.max_retries))
                time.sleep(2.0 ** attempt * 0.1)
            else:
                break
