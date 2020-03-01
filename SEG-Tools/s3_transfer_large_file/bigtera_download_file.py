#!/usr/bin/env python
# Author:Andy Zou <andy.zou@bigtera.com.cn>

from boto.s3.connection import S3Connection
from boto.s3.connection import OrdinaryCallingFormat
import os
from StringIO import StringIO
import configparser


HOST = '172.17.59.72'
S3_AK = 'JF06KCDJIAMO8Q3OJQAS'
S3_AS = 'gHnrKj1Vlb6s9IQZRrMDywhTLeNBL2UUMCGeetsf'
S3_BUCKET = 'andy_bucket'
S3_KEY = 'ubuntu-16.04-server-amd64.iso'
LOCAL_FILE = 'E:\\code\\s3_multipart_upload\\localfile.iso'

# Use a chunk size of 10 MiB (feel free to change this, >=5MB)
CHUNK_SIZE = 1024 * 1024 * 10


def create_s3_connection():
    c = S3Connection(calling_format=OrdinaryCallingFormat(),
                     host=HOST, is_secure=False,
                     aws_access_key_id=S3_AK,
                     aws_secret_access_key=S3_AS,
                     validate_certs=False)
    return c


def get_obj_io_ctx(s3_key_obj=None, offset=None, length=None):
    if s3_key_obj is None:
        return None
    io_ctx = StringIO()
    headers = None
    if offset is not None and length is not None:
        headers = {
            "Range": "bytes={}-{}".format(offset, offset+length-1)
        }
    s3_key_obj.get_contents_to_file(io_ctx, headers)
    io_ctx.seek(0)
    return io_ctx


def main():
    c = create_s3_connection()
    b = c.get_bucket(S3_BUCKET)

    key = S3_KEY
    config_file = '.' + os.path.basename(LOCAL_FILE) + '.conf'

    s3_key_obj = b.get_key(key)
    if s3_key_obj is None:
        print(key + " does't exists!")
        exit(1)

    total_file_size = s3_key_obj.size
    remaining = total_file_size

    part_size = CHUNK_SIZE
    part_num = 0

    config = configparser.ConfigParser()
    config.read(config_file)

    stored_total_file_size = config.getint("bigtera_config", "total_file_size", fallback=0)
    stored_chunk_size = config.getint("bigtera_config", "chunk_size", fallback=0)
    stored_downloaded_size = config.getint("bigtera_config", "downloaded_size", fallback=0)

    seek_first = False
    if stored_total_file_size == total_file_size and stored_chunk_size == CHUNK_SIZE:
        remaining = stored_total_file_size - stored_downloaded_size
        part_num = stored_downloaded_size / stored_chunk_size
        open_option = "r+b"
        seek_first = True
    else:
        open_option = "wb"

    with open(LOCAL_FILE, open_option) as f:
        while remaining > 0:
            offset = part_num * part_size
            length = min(remaining, part_size)
            s3_obj_io_ctx = get_obj_io_ctx(s3_key_obj, offset, length)
            if seek_first:
                f.seek(offset)
                seek_first = False
            f.write(s3_obj_io_ctx.read())
            remaining = remaining - length

            downloaded_size = offset + length
            percentage = int(downloaded_size * 100 / total_file_size)
            if percentage > 100:
                percentage = 100
            print(str(downloaded_size) + '/' + str(total_file_size) + '  ' + str(percentage) + '%')

            part_num += 1
            with open(config_file, 'w') as configfile:
                config['bigtera_config'] = {}
                config['bigtera_config']['total_file_size'] = str(total_file_size)
                config['bigtera_config']['chunk_size'] = str(CHUNK_SIZE)
                config['bigtera_config']['downloaded_size'] = str(downloaded_size)

                config.write(configfile)

            if total_file_size == downloaded_size:
                os.remove(config_file)


if __name__ == '__main__':
    main()
