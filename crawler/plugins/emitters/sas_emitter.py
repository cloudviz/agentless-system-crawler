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
        self.emit_interval_fpath = kwargs.get("emit_interval_filepath", "")
        # set emit interval
        if os.path.exists(self.emit_interval_fpath):
            try:
                with open(self.emit_interval_fpath) as fp:
                    interval = fp.read().rstrip('\n')
                interval_time = int(interval)
                self.emit_interval = interval_time
            except (ValueError, IOError):
                self.emit_interval = 0
        else:
            self.emit_interval = 0

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

    def gen_params(self, namespace='', features='', timestamp='',
                   access_group='', source_type=''):
        params = {}

        # reformat namespace and access_group for icp env
        parsed_namespace = namespace.split("/")
        if len(parsed_namespace) >= 2 and parsed_namespace[0] == "icp":
            # set an adequate k8s namespace
            access_group = parsed_namespace[1]
            # remove "icp/" string from namespace
            namespace = namespace[4:]
            assert namespace[0] != "/"
        logger.info("emit frame (namespace=%s)", namespace)

        params.update({'namespace': namespace})
        params.update({'access_group': access_group})
        params.update({'features': features})
        params.update({'timestamp': timestamp})

        # load source_type if env exists
        # live crawler should be set it as 'container' and
        # reg crawler should be set it as 'image'
        if 'SOURCE_TYPE' in os.environ:
            source_type = os.environ['SOURCE_TYPE']
            assert source_type == 'image' or source_type == 'container'
        params.update({'source_type': source_type})

        return params

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
        headers.update({'Authorization': 'Bearer ' + token})

        params = self.gen_params(namespace=namespace, features=features,
                                 timestamp=timestamp, source_type=system_type,
                                 access_group=access_group)

        self.url = self.url.replace('sas:', 'https:')

        verify = True
        if self.ssl_verification == "False":
            verify = False
            from requests.packages.urllib3.exceptions \
                import InsecureRequestWarning
            requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

        # set interval to avoid burst emit
        if int(self.emit_interval) > 0:
            logger.debug("wait %s sec...", self.emit_interval)
            time.sleep(int(self.emit_interval))

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
