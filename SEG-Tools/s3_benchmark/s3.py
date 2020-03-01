# -*- coding: utf-8 -*-

import boto
import boto.s3.connection
from boto.s3.key import Key

from utils import FakeFile
from logwrapper import logger
import config


class S3:
    def __init__(self, access_key, secret_key, host, uid):
        self.conn = boto.connect_s3(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            host=host,
            is_secure=False,
            calling_format=boto.s3.connection.OrdinaryCallingFormat())
        self.uid = uid

    @property
    def access_key(self):
        return self.conn.aws_access_key_id

    def create_bucket(self, name):
        return self.conn.create_bucket(name)

    def get_bucket(self, name, **kwargs):
        return self.conn.get_bucket(name, **kwargs)

    @staticmethod
    def upload(bucket, fake_file, name, meta=None):
        if not meta:
            meta = {}

        try:
            if fake_file.size <= config.MULTIPART_THRESH:
                k = Key(bucket)
                k.key = name
                k.metadata = meta
                k.set_contents_from_file(fake_file.get_file())
            else:
                mpu = bucket.initiate_multipart_upload(name, metadata=meta)
                try:
                    remaining = fake_file.size
                    part_num = 0
                    part_size = config.MULTIPART_THRESH

                    while remaining > 0:
                        offset = part_num * part_size
                        length = min(remaining, part_size)
                        file_part = fake_file.get_file(offset, length)
                        mpu.upload_part_from_file(file_part, part_num + 1)
                        remaining -= length
                        part_num += 1

                    mpu.complete_upload()
                except Exception:
                    mpu.cancel_upload()
                    raise
        except Exception as e:
            logger.error(e, exc_info=True)

    @staticmethod
    def download(bucket, name):
        k = bucket.get_key(name)
        if not k:
            return

        try:
            if k.size <= config.MULTIPART_THRESH:
                k.get_contents_as_string()  # don't need to store the value
            else:
                remaining = k.size
                offset = 0
                length = config.MULTIPART_THRESH
                end = offset + length - 1

                while remaining > 0:
                    headers = {'Range': 'bytes={}-{}'.format(offset, end)}
                    logger.debug('download [{}], header [{}]'.format(k.name, headers))
                    k.get_contents_as_string(headers=headers)
                    remaining -= length
                    offset += length
                    end += length

        except Exception as e:
            logger.error(e, exc_info=True)
        finally:
            return k.size


def upload(bucket, obj_size, name, meta=None):
    fake_file = FakeFile(obj_size)
    S3.upload(bucket, fake_file, name, meta)


def download(bucket, name):
    return S3.download(bucket, name)
