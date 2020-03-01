#!/usr/bin/env python
# Author:Andy Zou <andy.zou@bigtera.com.cn>

from boto.s3.connection import S3Connection
from boto.s3.connection import OrdinaryCallingFormat
from boto.s3.multipart import MultiPartUpload
import math
import os
from filechunkio import FileChunkIO
import hashlib
# import time


HOST = '172.17.59.72'
S3_AK = 'JF06KCDJIAMO8Q3OJQAS'
S3_AS = 'gHnrKj1Vlb6s9IQZRrMDywhTLeNBL2UUMCGeetsf'
S3_BUCKET = 'andy_bucket'

LARGE_FILE = 'E:\\code\\s3_multipart_upload\\ubuntu-16.04-server-amd64.iso'

# Use a chunk size of 10 MiB (feel free to change this, >=5MB)
CHUNK_SIZE = 1024 * 1024 * 10


def create_s3_connection():
    c = S3Connection(calling_format=OrdinaryCallingFormat(),
                     host=HOST, is_secure=False,
                     aws_access_key_id=S3_AK,
                     aws_secret_access_key=S3_AS,
                     validate_certs=False)
    return c


def query_pending_parts(b, key):
    response_all_multipart_upload = []

    # print('Current pending parts in S3:')
    multipart_uploads_filter = {'key_marker': key}
    all_multipart_uploads = b.get_all_multipart_uploads(**multipart_uploads_filter)
    for one_multipart_upload in all_multipart_uploads:
        response_multipart_upload = {'key': one_multipart_upload.key_name,
                                     'upload_id': one_multipart_upload.id,
                                     'parts': []
                                     }
        mp = MultiPartUpload(b)
        mp.key_name = one_multipart_upload.key_name
        mp.bucket_name = b.name
        mp.id = one_multipart_upload.id
        all_parts = mp.get_all_parts()
        one_multipart_upload_len = len(all_parts)
        print(' upload_id:' + one_multipart_upload.id + '   key:' + one_multipart_upload.key_name +
              '        parts:' + str(one_multipart_upload_len))
        # print('one_multipart_upload length:' + str(one_multipart_upload_len))
        for one_parts in all_parts:
            response_part = {
                'part_number': one_parts.part_number,
                'etag': one_parts.etag.replace('"', ''),
                'size': one_parts.size
            }
            response_multipart_upload['parts'].append(response_part)
        response_all_multipart_upload.append(response_multipart_upload)

    return response_all_multipart_upload


def upload_left(b, full_file_path, key, pending_multipart_upload, chunk_size):

    source_size = os.stat(full_file_path).st_size

    pending_upload_id = pending_multipart_upload['upload_id']
    # pending_key = pending_multipart_upload['key']

    mp = MultiPartUpload(b)
    mp.key_name = key
    mp.bucket_name = b.name
    mp.id = pending_upload_id

    # Use a chunk size of 10 MiB (feel free to change this)
    # chunk_size = 1024 * 1024 * 10
    # chunk_size = CHUNK_SIZE
    chunk_count = int(math.ceil(source_size / float(chunk_size)))

    # Send the file parts, using FileChunkIO to create a file-like object
    # that points to a certain byte range within the original file. We
    # set bytes to never exceed the original file size.
    for i in range(chunk_count):
        part_num = i + 1
        offset = chunk_size * i
        upload_bytes = min(chunk_size, source_size - offset)

        with FileChunkIO(full_file_path, 'r', offset=offset, bytes=upload_bytes) as fp:
            m = hashlib.md5()
            m.update(fp.readall())
            chunk_md5 = unicode(m.hexdigest())
            found_part = False
            for one_part in pending_multipart_upload['parts']:
                if part_num == one_part['part_number'] and \
                        upload_bytes == one_part['size'] and \
                        chunk_md5 == one_part['etag']:
                    # print(one_part)
                    found_part = True
                    break
            if found_part is True:
                # pass
                continue
            fp.seek(0)
            mp.upload_part_from_file(fp, part_num=part_num)
            print('%d/%d uploaded' % (part_num, chunk_count))

    try:
        # Finish the upload
        return mp.complete_upload()
    except Exception as e:
        mp.cancel_upload()
        raise e


def upload_large_file(b, full_file_path, key, chunk_size):
    # 100MB
    large_file_threshold = 100 * 1024 * 1024

    if chunk_size < 5 * 1024 * 1024:
        chunk_size = 5 * 1024 * 1024

    all_pending_multipart_uploads = query_pending_parts(b, key)

    # Get file info
    source_size = os.stat(full_file_path).st_size

    pending_multipart_upload = None
    for one_pending_multipart_upload in all_pending_multipart_uploads:
        # In real product,we need check file-key-upload_id relation
        if key == one_pending_multipart_upload['key']:
            pending_multipart_upload = one_pending_multipart_upload
            break

    if source_size >= large_file_threshold and pending_multipart_upload is not None:
        print('keep uploading!')
        return upload_left(b, full_file_path, key, pending_multipart_upload, chunk_size)
    else:
        print('No pending upload exits! Upload_from_beginning!')
        return upload_from_beginning(b, full_file_path, key, chunk_size)


def upload_from_beginning(b, full_file_path, key, chunk_size):

    source_size = os.stat(full_file_path).st_size

    # Create a multipart upload request
    mp = b.initiate_multipart_upload(key)
    # keep file-key-upload_id relation for production use
    print('Uploading file:' + full_file_path)
    print('Key in S3:' + key)
    print('upload_id:' + mp.id)
    print('--------------------')

    # Use a chunk size of 10 MiB (feel free to change this)
    # chunk_size = 1024 * 1024 * 10
    # chunk_size = CHUNK_SIZE
    chunk_count = int(math.ceil(source_size / float(chunk_size)))

    # Send the file parts, using FileChunkIO to create a file-like object
    # that points to a certain byte range within the original file. We
    # set bytes to never exceed the original file size.
    for i in range(chunk_count):
        part_num = i + 1
        offset = chunk_size * i
        upload_bytes = min(chunk_size, source_size - offset)
        with FileChunkIO(full_file_path, 'rb', offset=offset, bytes=upload_bytes) as fp:
            mp.upload_part_from_file(fp, part_num=part_num)

        print('%d/%d uploaded' % (part_num, chunk_count))
        # print('sleeping 1 second ...')
        # time.sleep(1)
    return mp.complete_upload()


def main():
    c = create_s3_connection()
    b = c.get_bucket(S3_BUCKET)

    full_file_path = LARGE_FILE
    key = os.path.basename(full_file_path)

    upload_large_file(b, full_file_path, key, CHUNK_SIZE)


if __name__ == '__main__':
    main()
