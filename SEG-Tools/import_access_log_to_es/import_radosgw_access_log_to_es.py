#!/usr/bin/env python
# -*- coding: utf-8 -*-

from boto.s3.connection import S3Connection
from boto.s3.connection import OrdinaryCallingFormat
from subprocess import check_output
import json
import re
import urllib
import datetime
from datetime import timedelta
import email.utils as eut
from elasticsearch import Elasticsearch
import hashlib
import time
import logging
from logging.handlers import RotatingFileHandler
import os
from ezs3.config import Ezs3CephConfig
from ezs3.cluster import ClusterManager
from ezs3.command import do_cmd
from ezs3.cluster import Role, RoleState
# from ezs3.kvstore import KVStore, KVStoreError
from boto.s3.bucket import Bucket
from multiprocessing import Pool
import configparser
import rados

logger = logging.getLogger(__name__)

g_es = None
g_s3_conn = None


class CronLock:
    def __init__(self, lock_file='/tmp/import_access_log.lock', timeout=600):
        self.lock_file = lock_file
        self.timeout = timeout

    def lock(self):
        logger.debug('lock:' + self.lock_file)
        if os.path.isfile(self.lock_file):
            time_now = int(time.time())
            time_file_created = int(os.path.getmtime(self.lock_file))
            if time_now - time_file_created > self.timeout:
                logger.warning('cron job is still running.dead?please check!')
                os.remove(self.lock_file)
                # return False
            else:
                logger.warning('cron job is still running. we can wait for a while.')
                return False

        open(self.lock_file, 'a').close()
        return True

    def unlock(self):
        logger.debug('unlock:' + self.lock_file)
        try:
            os.remove(self.lock_file)
        except:
            logger.exception('failed to unlock')


def get_obj_key(s3_conn=None, bucket_name='', key_name=''):
    if bucket_name == '' or key_name == '':
        return None

    s3_bucket = Bucket(connection=s3_conn, name=bucket_name)

    try:
        read_key = s3_bucket.get_key(key_name)
    except:
        logger.exception("get_key failed.key_name:" + key_name)
        return None

    return read_key


def get_oid(bucket_name='', key_name=''):
    raw_string = bucket_name + key_name.decode('utf-8')
    encoded_string = raw_string
    md5_oid = hashlib.md5(encoded_string.encode('utf-8')).hexdigest()

    return md5_oid


def get_document(obj_key=None):
    if obj_key is None:
        return None

    """
    try:
        acp = obj_key.get_acl()
    except:
        logger.exception("get_acl failed.")
        return None        
    """

    date_time = obj_key.last_modified
    last_modified_datetime = datetime.datetime(*eut.parsedate(date_time)[:6]) + datetime.timedelta(hours=8)
    str_last_modified_datetime = last_modified_datetime.strftime('%Y-%m-%d %H:%M:%S')

    doc = {
       "bucket": obj_key.bucket.name,
       "name": obj_key.name,
       # "owner": {
       #  "id": acp.owner.id,
       #  "display_name": acp.owner.display_name
       # },
       # "permissions" : [],
       "meta": {
         "size": obj_key.size,
         "mtime": str_last_modified_datetime,
         "etag": obj_key.etag.strip('"')
       },
       "user_meta": obj_key.metadata
     }
    # print(doc)

    # print acp.owner.id
    # print acp.owner.display_name

    return doc


def delete_doc_es(es=None, oid=''):
    try:
        res = es.delete(index='object', doc_type='_doc', id=oid)
    except KeyboardInterrupt:
        return
    except:
        logger.exception("delete object in es failed.oid:" + oid)
        return

    if 'result' in res and 'deleted' == res['result']:
        logger.debug('deleted.oid:' + oid)
    elif'result' in res and 'not_found' == res['result']:
        logger.debug('not_found.oid:' + oid)
    else:
        print(res)
        logger.debug('unknown result for.oid:' + oid)


def save_doc_es(es=None, s3_conn=None, access_log=None, key_name='', oid=''):
    obj_key = get_obj_key(s3_conn, access_log['bucket'], key_name)
    if obj_key is not None:

        doc = get_document(obj_key)
        if doc is None:
            return

        # return  # for test only
        try:
            res = es.index(index="object", doc_type='_doc', id=oid, body=doc)
        except KeyboardInterrupt:
            return
        except:
            logger.exception("save access log to es failed.oid:" + oid)
            return

        if 'result' in res and ('created' == res['result'] or 'updated' == res['result']):
            logger.debug('saved.oid:' + oid)
        else:
            print(res)
            logger.debug('unknown result for.oid:' + oid)


def handle_useful_doc(es=None, s3_conn=None, access_log=None):
    # print(access_log)

    # FIX ME:if bucket name is the same with dir name,there is bug
    if access_log['uri'].startswith('/' + access_log['bucket'] + '/'):
        # for http://domain.com/bucket_name/keyname
        key_name = access_log['uri'].replace('/' + access_log['bucket'] + '/', "", 1)
    else:
        # for http://bucket_name.domain.com/keyname
        key_name = access_log['uri'].lstrip('/')

    # for multipart upload complete
    if '?uploadId=' in key_name and access_log['operation'] == "POST":
        key_name = key_name.split('?')[0]

    user_id = access_log['user']
    # print(key_name)
    # print(urllib.unquote(key_name).decode("utf-8"))
    key_name = urllib.unquote(str(key_name))
    # print(urllib.unquote(str(key_name)))
    # print(key_name)

    oid = get_oid(access_log['bucket'], key_name)

    if access_log['operation'] == "PUT" or access_log['operation'] == "POST":
        save_doc_es(es, s3_conn, access_log, key_name, oid)
    elif access_log['operation'] == "DELETE":
        delete_doc_es(es, oid)
        pass
    else:
        logger.debug("unknown operation:" + access_log['operation'])


def handle_access_log(access_log=None):
    # https://docs.aws.amazon.com/AmazonS3/latest/API/RESTObjectOps.html

    es = g_es
    s3_conn = g_s3_conn
    # print(access_log)
    if access_log is None:
        return

    # filter special account
    if access_log['user'] == 'special_account':
        return
    # print(access_log['bucket'])
    # disable raw access log for performance
    # self.import_all_raw_log(access_log)

    # only handle newly saved raw log
    if access_log['operation'] == 'GET' \
            or access_log['operation'] == 'HEAD' \
            or access_log['operation'] == 'OPTIONS':
        # client get information.we don't need these operation
        return

    if access_log['http_status'][0] != '2':
        # failed operation
        return

    if access_log['uri'] == '/' or \
            access_log['uri'].startswith('/?'):
        # bucket operation
        return

    if access_log['bucket'] == '':
        # bucket operation:list buckets
        return

    if access_log['uri'] == '/' + access_log['bucket'] or \
            access_log['uri'].startswith('/' + access_log['bucket'] + '?'):
        # bucket operation
        return

    if access_log['uri'] == '/' + access_log['bucket'] + '/' or \
            access_log['uri'].startswith('/' + access_log['bucket'] + '/?'):
        # bucket operation
        # POST Object - It's useful,but we can't handle it.
        return

    if access_log['operation'] == 'POST' and '?restore' in access_log['uri']:
        # POST Object restore
        return

    if access_log['operation'] == 'DELETE' and '?uploadId=' in access_log['uri']:
        # Abort Multipart Upload
        return

    if '?tagging' in access_log['uri'] and \
            (access_log['operation'] == 'PUT' or access_log['operation'] == 'DELETE'):
        # PUT Object tagging - DELETE Object tagging
        return

    if '?uploads' in access_log['uri'] and access_log['operation'] == 'POST':
        # Initiate Multipart Upload
        return

    if '?delete' in access_log['uri'] and access_log['operation'] == 'POST':
        # Delete Multiple Objects  --It's useful,but we can't handle it.
        return

    if 'partNumber=' in access_log['uri'] and 'uploadId=' in access_log['uri'] \
            and access_log['operation'] == 'PUT':
        # Upload Part and  Upload Part - Copy
        return

    if access_log['operation'] == 'PUT' \
            or access_log['operation'] == 'POST' \
            or access_log['operation'] == 'DELETE':

        handle_useful_doc(es, s3_conn, access_log)

    else:
        pass


def import_all_raw_log(es=None, access_log=None):

    if access_log is not None:
        raw_string = access_log['uri'] + access_log['time']
        encoded_string = raw_string.encode('utf-8')
        log_id = hashlib.md5(encoded_string).hexdigest()
        access_log['time'] = access_log['time'][0:19]
        access_log['time_local'] = access_log['time_local'][0:19]
        # print(access_log['time'])

        # noinspection PyBroadException
        try:
            res = es.index(index="raw_access_log", doc_type='_doc', id=log_id, body=access_log)
        except KeyboardInterrupt:
            return False
        except:
            logger.exception("saved raw access log failed.")
            return False

        if 'result' in res and 'created' == res['result']:
            logger.debug('raw access log saved')
            return True
        else:
            logger.debug('raw save access log.unknown result.')

        return False


def handle_all_access_log(s3_host='', is_s3_secure=False, system_user=None):
    """
    parse useful log from index "access_log" to index "object" for query

    :param s3_host: s3 host name or ip
    :param is_s3_secure: use https or http
    :param system_user: system_user dictionary
    :return:
    """

    # kvstore = KVStore()
    s3_conn = S3Connection(calling_format=OrdinaryCallingFormat(),
                           host=s3_host, is_secure=is_s3_secure,
                           aws_access_key_id=system_user['access_key'],
                           aws_secret_access_key=system_user['secret_key'])
    global g_s3_conn
    g_s3_conn = s3_conn

    cluster = rados.Rados(conffile='/etc/ceph/ceph.conf')
    cluster.connect()

    try:
        ioctx = cluster.open_ioctx('.log')
    except rados.ObjectNotFound:
        logger.warning('No pool:.log')
        return

    obj_list_out = check_output(["/usr/bin/radosgw-admin", "log", "list"])
    obj_list = json.loads(obj_list_out)
    file_list = []
    for obj_file_key in obj_list:
        obj_file_key = obj_file_key.encode('ascii', 'ignore')
        # filename match
        if re.match(r'^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-', obj_file_key) is None:
            continue

        # list buckets or bad operation
        if re.match(r'^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}--', obj_file_key) is not None:
            continue

        # only handle latest two hours
        # delete old files?
        str_current_minute = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-")
        minutes_ago = datetime.datetime.now() + timedelta(minutes=-10)
        str_minutes_ago = minutes_ago.strftime("%Y-%m-%d-%H-%M-")

        if obj_file_key < str_minutes_ago or obj_file_key >= str_current_minute:
            continue

        try:
            import_start_time = ioctx.get_xattr(obj_file_key, "ist")
        except rados.NoData:
            import_start_time = None

        try:
            import_end_time = ioctx.get_xattr(obj_file_key, "iet")
        except rados.NoData:
            import_end_time = None

        if import_start_time is None:
            # never handled it,we should handle it.
            file_list.append(obj_file_key)
        elif import_end_time is not None:
            # we have handled the file,ignore it.
            continue
        elif import_start_time is not None and import_end_time is None \
                and int(import_start_time) < (int(time.time()) - 60*5):
            # dead before ?
            logger.warning('Dead?Again!Handle log file :' + obj_file_key)
            file_list.append(obj_file_key)
        elif import_start_time is not None and import_end_time is None \
                and int(import_start_time) >= (int(time.time()) - 60*5):
            # locked ?
            logger.warning('Maybe someone is handling log file :' + obj_file_key)
            continue
        else:
            logger.warning('Some thing is wrong with log file:' + obj_file_key)
            continue

    # sort files according to create time
    file_list = sorted(file_list)

    for obj_file_key in file_list:
        logger.info('handling log:' + obj_file_key)
        before_show_log = time.time()
        try:
            # set import start time as lock
            ioctx.set_xattr(obj_file_key, "ist", str(int(time.time())))
            logger.debug('handling access log file:' + obj_file_key)
            log_list_out = check_output(["/usr/bin/radosgw-admin", "log", "show",
                                         '--object=' + obj_file_key])
        except KeyboardInterrupt:
            return False
        except:
            logger.exception("show log object error for object:" + obj_file_key)
            return
        after_show_log = time.time()
        logger.info('log show time:' + str(after_show_log - before_show_log))

        pool = Pool(32)
        # Need large memory ?
        obj_log_list = json.loads(log_list_out)
        if "log_entries" in obj_log_list:
            logger.info(obj_file_key + ' records:' + str(len(obj_log_list["log_entries"])))
            for obj_log in obj_log_list["log_entries"]:
                # print(obj_log)
                # handle_access_log(es, s3_conn, obj_log)
                pool.apply_async(handle_access_log, (obj_log,))
        pool.close()
        pool.join()

        after_handle_log = time.time()
        ioctx.set_xattr(obj_file_key, "iet", str(int(after_handle_log)))
        logger.info('log handle time:' + str(after_handle_log - after_show_log))
        logger.info(obj_file_key + ' time costs:' + str(after_handle_log - before_show_log))

    ioctx.close()


def is_mon_leader():
    # myip = utils.get_interface_ipv4( Ezs3CephConfig().get_storage_interface())
    myip = Ezs3CephConfig().get_storage_ip()
    cluster_mgr = ClusterManager()

    is_leader = cluster_mgr.is_mon_leader(myip, timeout=10)

    return is_leader


def configure_logging():
    log_formatter = logging.Formatter('%(asctime)s %(levelname)-8s:%(message)s', "%Y-%m-%d %H:%M:%S")
    log_file = '/var/log/import_radosgw_access_log.log'

    log_handler = RotatingFileHandler(log_file, mode='a', maxBytes=100 * 1024 * 1024,
                                      backupCount=2, encoding=None, delay=0)
    log_handler.setFormatter(log_formatter)

    logger.addHandler(log_handler)
    logger.setLevel(logging.INFO)


def query_user_info(user_id=''):
    if user_id == '':
        return None

    try:
        user_info = check_output(["/usr/bin/radosgw-admin", "user", "info", '--uid=' + user_id])
    except KeyboardInterrupt:
        return None
    except:
        logger.exception("radosgw-admin get user info failed.user_id:" + user_id)
        return None

    obj_user_info = json.loads(user_info)
    if "keys" in obj_user_info and len(obj_user_info['keys']) >= 1:
        obj_user_info['access_key'] = obj_user_info['keys'][0]['access_key']
        obj_user_info['secret_key'] = obj_user_info['keys'][0]['secret_key']
        return obj_user_info

    return None


def get_one_system_user():
    user_list_out = check_output(["/usr/bin/radosgw-admin", "metadata", "list", "user"])
    user_list = json.loads(user_list_out)
    for user_id in user_list:
        one_system_user = query_user_info(user_id)
        if one_system_user is None:
            continue

        if 'system' in one_system_user and one_system_user['system'] == "true" \
                and one_system_user['email'] != '' and one_system_user['suspended'] == 0:
            return one_system_user

    return None


def get_first_radosgw_ip():
    # we need refine this function
    mon_leader = ClusterManager().get_mon_leader()

    return mon_leader.ip


def get_first_radosgw_ip_bak():
    # we need refine this function
    mon_leader = ClusterManager().get_mon_leader()
    alive_nodes = set([])
    for line in do_cmd('gstat -an1l', _host=mon_leader.ip).splitlines():
        alive_nodes.add(line.split()[0])

    if len(alive_nodes) > 0:
        return list(alive_nodes)[0]

    """
    for one_node in alive_nodes:
        role_status = Role(one_node).get('ezgateway')
        if RoleState.ENABLED == role_status:
            return one_node
    """

    return None


def get_es_config():
    config = configparser.ConfigParser()
    # dir_path = os.path.dirname(os.path.realpath(__file__))

    # config.read(dir_path + '/import_radosgw_access_log_to_es.conf')
    config.read('/etc/ezs3/import_radosgw_access_log_to_es.conf')
    try:
        hosts = config.get("elasticsearch", "hosts", fallback='localhost')
        username = config.get("elasticsearch", "username", fallback='username')
        password = config.get("elasticsearch", "password", fallback='password')
        scheme = config.get("elasticsearch", "scheme", fallback='http')
        port = config.getint("elasticsearch", "port", fallback=9200)

        logger.debug('hosts:' + hosts)
        logger.debug('username:' + username)
        logger.debug('scheme:' + scheme)
        logger.debug('port:' + str(port))

        hosts = hosts.split(',')

        config = {'hosts': hosts,
                  'username': username,
                  'password': password,
                  'scheme': scheme,
                  'port': int(port)
                  }

        return config
    except KeyboardInterrupt:
        return None
    except:
        logger.exception("read configuration failed")
        return None


def main():
    configure_logging()
    cron_lock = CronLock()
    if cron_lock.lock() is False:
        logger.warning('Get lock failed!Exit!')
        return

    logger.info('Programme started!')
    if is_mon_leader():
        logger.debug('I am mon leader.')

        es_config = get_es_config()
        if es_config is not None:
            obj_es = Elasticsearch(
                es_config['hosts'],
                http_auth=(es_config['username'], es_config['password']),
                scheme=es_config['scheme'],
                port=es_config['port'],
                sniff_on_start=True,
                sniff_on_connection_fail=True,
                sniffer_timeout=20
            )

            global g_es

            g_es = obj_es

            system_user = get_one_system_user()
            if system_user is not None:
                s3_host = get_first_radosgw_ip()
                if s3_host is not None:
                    logger.debug('using rados gateway:' + s3_host)
                    logger.info('handling access log ...')
                    handle_all_access_log(s3_host=s3_host, is_s3_secure=False, system_user=system_user)
                else:
                    logger.warning('Can not get rados gateway!!!')

            else:
                logger.warning('Can not get system user!!!')
        else:
            logger.warning('Can not get config!!!')
    else:
        logger.info('I am not mon leader.I don not do anything.')

    logger.info('Programme finished!')
    cron_lock.unlock()


if __name__ == '__main__':
    main()
