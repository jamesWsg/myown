# -*- coding: utf-8 -*-

from __future__ import division

import time
import traceback

from multiprocessing import Process, JoinableQueue, Lock, Value

from logwrapper import logger
import config


class Tasks:
    def __init__(self, process_num, handler=None, interval=0, need_summarize=False):
        self.task_q = JoinableQueue(20000)
        self.need_summarize = need_summarize
        self.interval = int(interval)   # second
        self.lock = Lock()

        # statistics
        self.total = Value('i', 0)
        self.successful = Value('i', 0)
        self.failed = Value('i', 0)
        self.download = Value('i', 0)
        self.upload = Value('i', 0)
        self.upload_total_size = Value('L', 0)          # Byte
        self.download_total_size = Value('L', 0)        # Byte
        self.upload_average_size = Value('d', 0.0)      # Byte
        self.download_average_size = Value('d', 0.0)    # Byte

        if not handler:
            handler = self._handler
        for _ in xrange(process_num):
            p = Process(target=handler)
            p.daemon = True
            p.start()

    def add_task(self, item):
        self.task_q.put(item)
        logger.debug('add task {}'.format(item))

    def join(self):
        self.task_q.join()

    def close(self):
        self.task_q.close()

    def _summarize(self, is_upload, successful, obj_size):
        with self.lock:
            self.total.value += 1
            if successful:
                self.successful.value += 1
                if is_upload:
                    self.upload_total_size.value += obj_size
                    self.upload.value += 1
                else:
                    self.download_total_size.value += obj_size
                    self.download.value += 1
            else:
                self.failed.value += 1

    def get_statistics(self):
        self.download_average_size.value = self.download_total_size.value / self.download.value if self.download.value else 0.0
        self.upload_average_size.value = self.upload_total_size.value / self.upload.value if self.upload.value else 0.0

        return {
            'total': self.total.value,
            'successful': self.successful.value,
            'failed': self.failed.value,
            'download': self.download.value,
            'download_total_size': self.download_total_size.value,
            'download_average_size': self.download_average_size.value,
            'upload': self.upload.value,
            'upload_total_size': self.upload_total_size.value,
            'upload_average_size': self.upload_average_size.value,
        }

    def _handler(self):
        while True:
            task = self.task_q.get()
            func, args = task[0], task[1:]
            retry = config.RETRY
            obj_size = 0
            while retry > 0:
                try:
                    obj_size = func(*args)  # obj_size is None for upload operation
                    logger.debug('run: {}({}), retry: {}'.format(func.__name__, args, retry))
                    if self.need_summarize:
                        # report.info('Success: run: {}({}), retry: {}'.format(func.__name__, args, retry))
                        is_upload = func.__name__ == 'upload'
                        successful = True
                        obj_size = args[1] if is_upload else obj_size
                        self._summarize(is_upload, successful, obj_size)
                    break
                except Exception as e:
                    logger.error('fail: {}({}) retry: {}\n{}'.format(func.__name__, args, retry, e))
                    logger.error(traceback.format_exc())
                    retry -= 1
            if retry < 1:
                logger.critical('{}({}) failed after {} retries'.format(func.__name__, args, config.RETRY))
                if self.need_summarize:
                    # report.error('Failed: {}({}) failed after {} retries'.format(func.__name__, args, config.RETRY))
                    is_upload = func.__name__ == 'upload'
                    successful = False
                    obj_size = args[1] if is_upload else obj_size
                    self._summarize(is_upload, successful, obj_size)

            if self.interval:
                time.sleep(self.interval)

            self.task_q.task_done()
