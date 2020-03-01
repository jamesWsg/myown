#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from __future__ import division

import os
import sys
import random
import time
import traceback
cwd = os.path.dirname(__file__)
local_lib = os.path.join(cwd, 'libs/lib/python2.7/site-packages')
if local_lib not in sys.path:
    sys.path.insert(0, local_lib)   # make sure using local 'requests' and 'boto' module instead of system's default

import config
from s3 import S3, download, upload
from utils import get_accounts, humanize_size, humanize_time
from logwrapper import logger
from mp_tasks import Tasks


class Benchmark:
    def __init__(self, s3_list):
        self.tasks = Tasks(config.CONCURRENCY, interval=config.OPERATION_INTERVAL, need_summarize=True)
        self.s3_list = s3_list
        self.duration = None

    def add_upload_task(self):
        s3 = random.choice(self.s3_list)
        bucket_id = random.randrange(0, config.BUCKET_PER_ACCOUNT)
        if config.OVERWRITE_OLD_FILE:
            object_id = random.randrange(config.OBJECT_PER_BUCKET, 2 * config.OBJECT_PER_BUCKET)
        else:
            object_id = time.time()
        bucket_name = s3.uid + config.BUCKET_PREFIX + str(bucket_id)
        bucket = s3.get_bucket(bucket_name, validate=False)
        obj_name = bucket_name + config.OBJECT_PREFIX + str(object_id)
        obj_size = random.randint(config.MIN_FILE_SIZE, config.MAX_FILE_SIZE)
        logger.debug('add upload: {} {} {}'.format(bucket, obj_size, obj_name))
        self.tasks.add_task((upload, bucket, obj_size, obj_name))

    def add_download_task(self):
        s3 = random.choice(self.s3_list)
        bucket_id = random.randrange(0, config.BUCKET_PER_ACCOUNT)
        object_id = random.randrange(0, config.OBJECT_PER_BUCKET)
        bucket_name = s3.uid + config.BUCKET_PREFIX + str(bucket_id)
        bucket = s3.get_bucket(bucket_name, validate=False)
        obj_name = bucket_name + config.OBJECT_PREFIX + str(object_id)
        logger.debug('add download: {} {}'.format(bucket, obj_name))
        self.tasks.add_task((download, bucket, obj_name))

    @staticmethod
    def next_task_is_upload():
        upload_chance = config.UPLOAD_RATE / (config.UPLOAD_RATE + config.DOWNLOAD_RATE)
        return random.random() < upload_chance

    def generate_report(self):
        statistics = self.tasks.get_statistics()

        # turn 10485760 Bytes to 10 MB for better reading experience
        for name in ('download_total_size', 'download_average_size', 'upload_total_size', 'upload_average_size'):
            size, unit = humanize_size(statistics[name])
            statistics[name] = {'size': size, 'unit': unit}

        divider = '-' * 80
        duration, unit = humanize_time(self.duration)
        report = 'Overall: {:.1f} {}, {} operations, Success {}, Failure {}\n' \
                 '{}\n' \
                 'Download {:8} times, total {:7.2f} {}, average {:7.2f} {}\n' \
                 'Upload   {:8} times, total {:7.2f} {}, average {:7.2f} {}'.format(
                     duration, unit, statistics['total'], statistics['successful'], statistics['failed'],
                     divider, statistics['download'],
                     statistics['download_total_size']['size'], statistics['download_total_size']['unit'],
                     statistics['download_average_size']['size'], statistics['download_average_size']['unit'],
                     statistics['upload'],
                     statistics['upload_total_size']['size'], statistics['upload_total_size']['unit'],
                     statistics['upload_average_size']['size'], statistics['upload_average_size']['unit']
                 )
        return '{:=^80}\n{}\n{:=^80}'.format(' S3 Benchmark ', report, ' End ')

    def start(self):
        now = time.time()
        while time.time() - now < config.TEST_DURATION:
            if self.next_task_is_upload():
                self.add_upload_task()
            else:
                self.add_download_task()

        self.tasks.join()
        self.duration = time.time() - now


if __name__ == '__main__':
    if config.PREPARE:
        from prepare import prepare
        prepare()
        logger.info('prepare done')

        choice = raw_input('Prepare done, start test?(y/[n])')
        if choice.strip().lower() != 'y':
            sys.exit()

    s3_list = [S3(access_key, secret_key, config.HOST, uid)
               for access_key, secret_key, uid in get_accounts()]

    benchmark = Benchmark(s3_list)
    try:
        benchmark.start()
    except KeyboardInterrupt:
        print 'Programe terminated.'
    except Exception as e:
        print(e)
        logger.error(e)
        logger.error(traceback.format_exc())
    finally:
        benchmark.tasks.close()
        print benchmark.generate_report()
        sys.exit()
