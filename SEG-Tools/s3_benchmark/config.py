# -*- coding: utf-8 -*-

import os
import json

ROOT = os.path.dirname(__file__)
config_file = os.path.join(ROOT, 'config.json')
with open(config_file) as reader:
    config = json.load(reader)


# host settings
HOST = config['host']

# file settings
MIN_FILE_SIZE = config['min_file_size']  # Byte
MAX_FILE_SIZE = config['max_file_size']  # Byte

# runtime settings
CONCURRENCY = config['concurrency']

# s3 settings
ACCOUNTS = config.get('accounts', [])
ACCOUNT_QUANTITY = config.get('account_quantity', 1)
ACCOUNT_PREFIX = config.get('account_prefix', 'account')

BUCKET_PER_ACCOUNT = config.get('bucket_per_account', 5)
assert BUCKET_PER_ACCOUNT <= 1000      # 单个账户下，桶的数量不允许超过1000
BUCKET_QUANTITY = BUCKET_PER_ACCOUNT * ACCOUNT_QUANTITY
BUCKET_PREFIX = config.get('bucket_prefix', 'bucket')

OBJECT_PER_BUCKET = config.get('object_per_bucket', 100)
OBJECT_PREFIX = config.get('object_prefix', 'object')

# META_DATA ?

# test settings
PREPARE = config.get('prepare', True)
TEST_DURATION = config.get('test_duration', 259200)         # seconds
OPERATION_INTERVAL = config.get('operation_interval', 120)  # seconds
MULTIPART_THRESH = config.get('multipart_thresh', 10485760)
DOWNLOAD_RATE = config.get('download_rate', 1)
UPLOAD_RATE = config.get('upload_rate', 1)
RETRY = config.get('retry', 3)
OVERWRITE_OLD_FILE = config.get('overwrite_old_file', True)
