# -*- coding: utf-8 -*-

from __future__ import division

import requests

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import config


requests.packages.urllib3.disable_warnings()  # disable warning of https verify being disabled


class FakeFile:
    def __init__(self, size=10485760):
        self.obj = StringIO('\x00' * size)
        self.size = size    # byte

    def get_file(self, offset=None, length=None):
        if offset is not None:
            self.obj.seek(offset)
        if length:
            return StringIO(self.obj.read(length))
        else:
            return self.obj

    def read(self):
        return self.obj.read()

    def __repr__(self):
        return 'file of size {}'.format(self.size)


def login():
    session = requests.Session()
    url = 'https://' + config.HOST + ':8080/cgi-bin/ezs3/json/login'
    params = {'user_id': 'admin', 'password': '1'}
    session.get(url, params=params, verify=False)
    return session


def get_accounts(session=None):
    if not session:
        session = login()
    url = 'https://' + config.HOST + ':8080/cgi-bin/ezs3/json/user_list'
    response = session.get(url, verify=False)
    users = response.json()['response']['account_list']['user']
    return [(u['access_key'], u['secret_key'], u['uid'])
            for u in users if u['uid'].startswith(config.ACCOUNT_PREFIX)]


def humanize_size(size, unit='Byte'):
    units = {'Byte': 'KB', 'KB': 'MB', 'MB': 'GB', 'GB': 'TB', 'TB': 'PB', 'PB': 'EB'}
    if unit not in units:
        raise ValueError('Unsupported unit [{}]'.format(unit))

    while unit != 'PB':
        if size < 1024:
            break
        else:
            size /= 1024
            unit = units[unit]

    return size, unit


def humanize_time(time, unit='second'):
    units = {'second': 'minute', 'minute': 'hour', 'hour': 'day', 'day': 'month'}
    if unit not in units:
        raise ValueError('Unsupported unit [{}]'.format(unit))

    while unit != 'day':
        if unit in ('second', 'minute'):
            if time >= 60:
                time /= 60
                unit = units[unit]
            else:
                break
        else:  # hour
            if time >= 24:
                time /= 24
                unit = units[unit]
            else:
                break

    if time != 1:
        unit += 's'

    return time, unit
