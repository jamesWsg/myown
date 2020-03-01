#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import requests
import logging.config
from datetime import datetime, timedelta


host = '172.16.146.228'
user_name = 'admin'
password = '1'
max_log_size = 20 * 1024 * 1024  # 20MB
max_log_backups = 10

base_dir = os.path.dirname(__file__)
log_file = os.path.join(base_dir, 'central.log')
last_run_file = os.path.join(base_dir, 'last_run')

now = datetime.now().strftime('%m/%d/%Y %H:%M')
now_date, now_time = now.split(' ')


def get_session():
    # login to get session
    login_url = 'https://{}:8080/cgi-bin/ezs3/json/login'.format(host)
    session = requests.Session()
    session.get(login_url, params={'user_id': user_name, 'password': password}, verify=False)
    return session


def get_log(session):
    # send request to get log
    get_log_url = 'https://{}:8080/cgi-bin/ezs3/json/central_log_get'.format(host)

    try:
        with open(last_run_file) as reader:
            last_run_str = reader.read().strip()
            last_run_date, last_run_time = last_run_str.split(' ')
    except IOError:
        # if last run file does not exist, set last_run_date to 1 week ago
        one_week_ago = datetime.now() - timedelta(days=7)
        last_run_date = one_week_ago.strftime('%m/%d/%Y')
        last_run_time = ''

    params = {
        'categories': '',
        'events': '',
        'severities': 'INFO',
        'start_date': last_run_date,
        'start_time': last_run_time,
        'end_date': now_date,
        'end_time': now_time,
        'export_log': 'false',
        'export_name': ''
    }
    response = session.get(get_log_url, params=params, verify=False)
    return response.json()['response']['logs']


def write_log_to_file(logs):
    logging.config.dictConfig({
        'version': 1,
        'formatters': {
            'default': {
                'format': '%(message)s'
            },
        },
        'handlers': {
            'file': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'default',
                'filename': log_file,
                'maxBytes': max_log_size,
                'backupCount': max_log_backups,
                'encoding': 'utf-8'
            },
        },
        'loggers': {
            'central': {
                'handlers': ['file'],
                'level': 'INFO',
                'propagate': True
            }
        }
    })
    logger = logging.getLogger('central')
    log_format = '[{log_time}] [{log_host}] [{log_category}] [{log_event}] {log_data}'
    for log in logs:
        logger.info(log_format.format(**log))


def record_last_run(now):
    # store time of last run
    with open(last_run_file, 'w') as writer:
        writer.write(now)


if __name__ == '__main__':
    session = get_session()
    logs = get_log(session)
    write_log_to_file(logs)
    record_last_run(now)
