import cStringIO
import gzip
import sys
import os
import tempfile
from minio import Minio
from minio.error import (ResponseError, BucketAlreadyOwnedByYou,
                         BucketAlreadyExists)
import json
import urllib3
import requests

from iemit_plugin import IEmitter


class COSEmitter(IEmitter):

    def get_emitter_protocol(self):
        return 'cos'

    def emit(self, frame, compress=False,
             metadata={}, snapshot_num=0, **kwargs):
        """

        :param iostream: a CStringIO used to buffer the formatted features.
        :param compress:
        :param metadata:
        :param snapshot_num:
        :return:
        """
        iostream = self.format(frame)
        compress = True
        iostream.seek(0)
        print "args ", kwargs
        self.cos_accesskey_filepath = kwargs.get("cos_accesskey_filepath", "")
        self.cos_secretkey_filepath = kwargs.get("cos_secretkey_filepath", "")
        self.cos_location_filepath = kwargs.get("cos_location_filepath", "")

        if self.emit_per_line:
            proto = self.get_emitter_protocol()
            raise NotImplementedError(
                '%s emitter does not support per feature emit ' % proto
            )
        elif compress == False:
            proto = self.get_emitter_protocol()
            raise NotImplementedError(
                '%s emitter support only compress ' % proto
            )

        for line in iostream.readlines():
            if line.startswith('metadata'):
               mdJson = json.loads(line.split()[2])
               break
               
        self.emit_string(iostream.getvalue().strip(), mdJson)
    
    def get_cos_tokens(self):
        print self.cos_accesskey_filepath
        assert(os.path.exists(self.cos_accesskey_filepath))
        assert(os.path.exists(self.cos_secretkey_filepath))
        assert(os.path.exists(self.cos_location_filepath))

        fp = open(self.cos_accesskey_filepath)
        accesskey = fp.read().rstrip('\n')
        fp.close()

        fp = open(self.cos_secretkey_filepath)
        secretkey = fp.read().rstrip('\n')
        fp.close()

        fp = open(self.cos_location_filepath)
        location = fp.read().rstrip('\n')
        fp.close()

        return(accesskey, secretkey, location)

    def emit_string(self, frameStr, mdJson):
        #print frameStr
        tmpfilepath = tempfile.NamedTemporaryFile(prefix="frame", suffix=".gz")
        #print tmpfilepath.name
        tempio = cStringIO.StringIO()
        gzip_file = gzip.GzipFile(fileobj=tempio, mode='w')
        gzip_file.write(frameStr)
        gzip_file.close()
        tmpfp = open(tmpfilepath.name, "w")
        #print tempio.getvalue()
        tmpfp.write(tempio.getvalue())
        tmpfp.close()
        timestamp = mdJson['timestamp']
        hostType = mdJson.get('hostType', 'worker')
        hostNamespace = mdJson['namespace']
        objPath = "%s/%s/%s.gz"%(hostType, hostNamespace, timestamp)
        #print objPath
        #print self.url
        cosUrl = self.url.replace('cos://','').split('/')
        if len(cosUrl) != 2:
           return
        
        cosBucket = cosUrl[len(cosUrl)-1]
        cosConn = cosUrl[0]
        print "Cos Bucket %s Cos Connectection %s"%(cosBucket, cosConn)
        hc = urllib3.PoolManager(cert_reqs='NONE')

        
        (accesskey, secretkey, location) = self.get_cos_tokens()
        # Initialize minioClient with an endpoint and access/secret keys.
        minioClient = Minio(cosConn,
                       access_key=accesskey,
                       secret_key=secretkey,
                       secure=True,
                       http_client = hc)
        urllib3.disable_warnings()
        requests.packages.urllib3.disable_warnings()
        
        # Make a bucket with the make_bucket API call.
        try:
             minioClient.make_bucket(cosBucket, location=location)
        except BucketAlreadyOwnedByYou as err:
             pass
        except BucketAlreadyExists as err:
             pass
        except ResponseError as err:
             print err
             raise
        # upload frame to bucket 
        try:
             minioClient.fput_object(cosBucket, objPath, tmpfilepath.name)
        except ResponseError as err:
             print err
             raise
        finally:
            os.remove(tmpfilepath.name)
