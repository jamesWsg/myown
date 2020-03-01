# -*- coding: utf-8 -*-

import traceback
import random

import config
from s3 import S3, FakeFile
from mp_tasks import Tasks
from utils import login, get_accounts
from logwrapper import logger


def create_account(suffix, session):
    name = config.ACCOUNT_PREFIX + str(suffix)
    url = 'https://' + config.HOST + ':8080/cgi-bin/ezs3/json/add_user'
    params = {
        'user_id': name,
        'display_name': name,
        'email': name + '@test.com',
        'password': 'test',
        'confirm_password': 'test',
    }
    try:
        session.get(url, params=params, verify=False)
    except Exception as e:
        logger.error('create account [{}] failed'.format(name))
        logger.error(e)


def create_bucket(suffix, username, s3):
    # 同一集群中，桶不允许重名，无论是不是属于同一个用户
    name = username + config.BUCKET_PREFIX + str(suffix)
    try:
        s3.create_bucket(name)
    except Exception as e:
        logger.error('create bucket [{}] failed, account [{}]'.format(name, s3.access_key))
        logger.error(e)
        logger.error(traceback.format_exc())


def create_object(suffix, s3, bucket, size):
    obj = FakeFile(size)
    name = bucket.name + config.OBJECT_PREFIX + str(suffix)
    try:
        s3.upload(bucket, obj, name)
    except Exception as e:
        logger.error('create file [{}] failed, bucket [{}], account [{}]'.format(
            name, bucket.name, s3.access_key
        ))
        logger.error(e)


tasks = Tasks(config.CONCURRENCY)


def prepare():
    session = login()

    logger.info('Create accounts ...')
    for i in range(config.ACCOUNT_QUANTITY):
        tasks.add_task((create_account, i, session))

    tasks.join()
    users = get_accounts(session)

    logger.info('Create buckets ...')
    s3_list = []
    for access_key, secret_key, uid in users:
        s3 = S3(access_key, secret_key, config.HOST, uid)
        s3_list.append(s3)
        for i in range(config.BUCKET_PER_ACCOUNT):
            tasks.add_task((create_bucket, i, uid, s3))
    tasks.join()

    logger.info('Create objects ...')
    for s3 in s3_list:
        for i in xrange(config.BUCKET_PER_ACCOUNT):
            bucket = s3.get_bucket(s3.uid + config.BUCKET_PREFIX + str(i))
            for j in xrange(config.OBJECT_PER_BUCKET):
                size = random.randint(config.MIN_FILE_SIZE, config.MAX_FILE_SIZE)
                tasks.add_task((create_object, j, s3, bucket, size))

    tasks.join()
    tasks.close()


if __name__ == '__main__':
    import os
    import sys

    cwd = os.path.dirname(__file__)
    local_lib = os.path.join(cwd, 'libs/lib/python2.7/site-packages')
    if local_lib not in sys.path:
        sys.path.insert(0, local_lib)  # make sure using local 'requests' and 'boto' module instead of system's default

    prepare()
    sys.exit()
