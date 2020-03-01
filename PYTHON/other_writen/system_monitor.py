#!/usr/bin/env python

import os
import sys
import time
import json
import logging
import StringIO
import traceback
from ezs3 import kvstore
from ezs3.log import EZLog
from ezs3.daemon import Daemon
from ezs3.command import do_cmd
from ezs3.config import Ezs3CephConfig
from ezs3.cluster import ClusterManager, Role, RoleState, GW, RRS
from ezs3.defaults import BigTeraDefaultSettings as defaults
from ezs3.notifications import BigTeraNotificationSettings as notifications
from ezs3.utils import readfile, get_interface_ipv4, get_mdsmap,send_notification

SYS_NOTIFICATION_MGR_PIDFILE="/var/run/system_notification.pid"
SYSTEM_NOTIFICATION_CHECK_INTERVAL = 60

EZLog.init_handler(logging.INFO, "/var/log/ezcloudstor/sysmon.log")
logger = EZLog.get_logger(__name__)

conf =  Ezs3CephConfig()
myip = get_interface_ipv4(conf.get_storage_interface())


def send_alert_mail(title, message):
    logger.debug("send alert mail")

    product = readfile(defaults.PROD_INFO_PATH_PRODUCT)
    company = readfile(defaults.PROD_INFO_PATH_VENDOR)

    conf =  Ezs3CephConfig()
    myip = get_interface_ipv4(conf.get_storage_interface())

    title = "[{} {}-{} Alert] {}".format(company, product, myip, title)

    time_string = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    message = "{} \n\n\nThis Mail is generate at time:{}".format(message,time_string)

    logger.debug("Title {}".format(title))
    logger.debug("Message {}".format(message))
    try:
        info = {}
        info["email_sender"] = notifications.email_sender
        info["email_list"] = notifications.email_list
        info["full_ratio"] = notifications.full_ratio
        info["smtp_server"] = notifications.smtp_server
        info["smtp_encrypt"] = notifications.smtp_encrypt
        info["smtp_auth"] = notifications.smtp_auth
        info["smtp_auth_user"] = notifications.smtp_auth_user
        info["smtp_auth_passwd"] = notifications.smtp_auth_passwd

        send_notification(title, message, info)
        return True
    except Exception as e:
        logger.error("cannot send the notification email: %s", str(e))
        logger.error(traceback.format_exc())
        return False


def check_dry_run(param_dict):
    last_notify = (param_dict['last_notify'])
    notify_frequency = (param_dict['notify_frequency'])*60

    time_stamp = time.time()
    if last_notify + notify_frequency  > time_stamp + 1:
        return True
    else:
        return False

def check_pre_process(param_dict):
    dry_run = check_dry_run(param_dict)

    time_stamp = time.time()
    param_dict['last_check'] = time_stamp

    return dry_run

def check_dry_run_and_update_last_check(param_dict):
    dry_run = check_dry_run(param_dict)

    time_stamp = time.time()
    param_dict['last_check'] = time_stamp

    return dry_run

def check_post_process(will_send, param_dict, hit_log, miss_log,title, content):
    dry_run = check_dry_run_and_update_last_check(param_dict)

    if will_send:
        logger.error("{}".format(hit_log))
        if dry_run:
            pass
        else:
            ret = send_alert_mail(title, content)
            if ret is True:
                time_stamp = time.time()
                param_dict['last_notify'] = time_stamp
            else:
                logger.error("send alert mail failed")
    else:
        logger.info("{}".format(miss_log))


###############################################################################
def check_process_num(param_dict):
    will_send = False

    raw = do_cmd("ps ax |wc -l |tr -d '\n'")
    process_num = int(raw)

    if process_num > notifications.PROCESS_NUM_THRESHOLD:
        will_send = True

    HIT_LOG = "Too Many Process EXISTS : {}".format(raw)
    MISS_LOG = "Check Process Num :{}, OK".format(raw)
    MAIL_TITLE = "Too Many Process Exists"
    MAIL_CONTENT = "There are {} Processes in this storage node".format(raw)

    check_post_process(will_send, param_dict,HIT_LOG, MISS_LOG, MAIL_TITLE, MAIL_CONTENT)


def check_high_mem_process(param_dict):

    will_send = False
    
    # get high mem process top 5
    raw = do_cmd("ps aux |sort -nrk 4|head -n 5")
    buf = StringIO.StringIO(raw)

    total_rsz = 0
    line = buf.readline()
    while line:
        line_array = line.split()
        cur_vsz = int(line_array[4])/1024
        cur_rsz = int(line_array[5])/1024

        if cur_rsz > notifications.SINGLE_PROCESS_RSZ_THRESHOLD or \
           cur_vsz > notifications.SINGLE_PROCESS_VSZ_THRESHOLD:
            will_send = True
        # only check the top 1, and break
        break


    HIT_LOG = "High-Mem usage Process EXISTS \n {}".format(raw)
    MISS_LOG = "Check High-Mem Process done, OK".format(raw)
    MAIL_TITLE = "High-Mem usage Process Exists"
    MAIL_CONTENT = "These are top 5 High memory usage Processes: \n {}".format(raw)

    check_post_process(will_send, param_dict,HIT_LOG, MISS_LOG, MAIL_TITLE, MAIL_CONTENT)

def check_loadavg(param_dict):

    will_send = False

    with open("/proc/loadavg") as f:
        for line in f.readlines():
            load_1_minute = float(line.split()[0])
            load_5_minute = float(line.split()[1])
            load_15_minute = float(line.split()[2])
            break

    if load_1_minute > notifications.LOADAVG_HIGH_1_MINUTE_THREASHOLD and \
       load_5_minute > notifications.LOADAVG_HIGH_5_MINUTE_THREASHOLD:
        will_send = True

    HIT_LOG = "High CPU loadavg {} {} {}".format(load_1_minute, load_5_minute, load_15_minute)
    MISS_LOG = "Check CPU loadavg done : {} {} {}, OK".format(load_1_minute, load_5_minute, load_15_minute)
    MAIL_TITLE = "High CPU Loadavg"
    MAIL_CONTENT = "This is CPU loadavg in this storage node: \n {} {} {}".format(load_1_minute,load_5_minute,load_15_minute)

    check_post_process(will_send, param_dict,HIT_LOG, MISS_LOG, MAIL_TITLE, MAIL_CONTENT)

################################################################################
def check_free_memory(param_dict):
    will_send = False

    total_mem_mb = 0
    avail_mem_mb = 0
    with open("/proc/meminfo") as f:
        for line in f.readlines():
            if line.startswith("MemTotal"):
                total_mem_mb = int(line.split()[1])/1024
                continue
            if line.startswith("MemAvailable"):
                avail_mem_mb = int(line.split()[1])/1024
                break
    
    if total_mem_mb > notifications.TOTAL_MEM_LOW_THRESHOLD and \
       avail_mem_mb < notifications.FREE_MEM_LOW_THRESHOLD:                   # Program cost more than 40G
        will_send = True

    HIT_LOG = "Avail Memory is less than 20G({} MB), buffer+cache included".format(avail_mem_mb)
    MISS_LOG = "Check Avail Memory done ({} MB), OK".format(avail_mem_mb)
    MAIL_TITLE = "Low Memory Available"
    MAIL_CONTENT = "{} MB memory Available.\nPlease Check your programs' memory usage'".format(avail_mem_mb)

    check_post_process(will_send, param_dict,HIT_LOG, MISS_LOG, MAIL_TITLE, MAIL_CONTENT)
            

def check_os_partition_usage(param_dict):
    will_send = False

    st = os.statvfs("/")
    free = (st.f_bavail * st.f_frsize)
    total = (st.f_blocks * st.f_frsize)

    used = (st.f_blocks - st.f_bfree) * st.f_frsize
    used_percent = float(used)/total*100 

    if used_percent > notifications.OS_PARTITION_USED_THRESHOLD:
        will_send = True

    HIT_LOG = "OS Partition Usage too High: {} percent".format(used_percent)
    MISS_LOG = "OS Partition Usage is {} percent, OK".format(used_percent)

    MAIL_TITLE = "OS Partition Usage too High"
    MAIL_CONTENT = "{} percent Space is used up".format(used_percent)

    check_post_process(will_send, param_dict, HIT_LOG,MISS_LOG,MAIL_TITLE,MAIL_CONTENT)

def check_readonly_os_partition(param_dict):
    will_send = False
    
    with open('/proc/mounts','r') as f:
        for line in f.readlines():
            current = line.split()
            if current[1] == "/":
                options = current[3].split(',')
                if "ro" in options:
                    will_send = True
                break
    
    HIT_LOG="OS FileSystem become READONLY"
    MISS_LOG="OS FileSystem is not RO, OK"
    MAIL_TITLE="OS Filesystem READONLY"
    MAIL_CONTENT="Please Check kern.log for EXT4 error or remount OS partitions"

    return check_post_process(will_send, param_dict, HIT_LOG, MISS_LOG, MAIL_TITLE, MAIL_CONTENT)

##############################################################################
RELATED_PROCESS =  [
        {"name":"winbindd", "p_type":0, "pid_num": 0,"pid_file":"/var/run/samba/winbindd.pid","last_notify":0,"notify_frequency":1440},
        {"name":"smbd", "p_type":0,   "pid_num": 0,"pid_file":"/var/run/samba/smbd.pid","last_notify":0,"notify_frequency":1440},
        {"name":"nmbd", "p_type":0, "pid_num": 0,"pid_file":"/var/run/samba/nmbd.pid","last_notify":0,"notify_frequency":1440},
        # general related
        {"name":"ezmonitor", "p_type":1, "pid_num": 0,"pid_file":"/var/run/ezmonitor.pid","last_notify":0,"notify_frequency":1440},
        {"name":"ezs3-agent","p_type":1, "pid_num": 0,"pid_file":"/var/run/ezs3-agent.pid","last_notify":0,"notify_frequency":1440},
        {"name":"ezgwvm", "p_type":1,"pid_num": 0,"pid_file":"/var/run/ezgwvmd.pid","last_notify":0,"notify_frequency":1440},
        {"name":"ezqos", "p_type":1,"pid_num": 0,"pid_file":"/var/run/ezqos.pid","last_notify":0,"notify_frequency":1440},
        {"name":"ezsnapsched", "p_type":1,"pid_num": 0,"pid_file":"/var/run/ezsnapsched.pid","last_notify":0,"notify_frequency":1440},
        {"name":"ezs3-multiregion-agent", "p_type":1,"pid_num": 0,"pid_file":"/var/run/ezs3-multiregion-agent.pid","last_notify":0,"notify_frequency":1440},
        # GW related
        {"name":"eziscsi","p_type":2, "pid_num": 0,"pid_file":"/var/run/eziscsid.pid","last_notify":0,"notify_frequency":1440},
        {"name":"ezfs-agent", "p_type":2,"pid_num": 0,"pid_file":"/var/run/ezfs-agent.pid","last_notify":0,"notify_frequency":1440},
        {"name":"eziscsi-rbd-cleaner", "p_type":2,"pid_num": 0,"pid_file":"/var/run/eziscsi-rbd-cleaner.pid","last_notify":0,"notify_frequency":1440},
        # RRS related
        {"name":"ezbackup-agent","p_type":3, "pid_num": 0,"pid_file":"/var/run/ezbackup-agent.pid","last_notify":0,"notify_frequency":1440},
]

def update_hit_result(bitmap,pid_not_exist,pid_changed,item):

    if pid_not_exist is False and pid_changed is False:
        return 

    if pid_not_exist is True and pid_changed is True:
        return

    name = item["name"]
    notify_frequency = int(item["notify_frequency"])*60
    last_notify = int(item["last_notify"])

    time_stamp = time.time()
    logger.debug("{} notify_frequency {} last_notify {} time_stamp {}".format(name, notify_frequency,last_notify,time_stamp))

    result = {}
    if time_stamp - last_notify + 1 > notify_frequency:
        result["name"] = name
        if pid_not_exist:
            result["event"] = "This Process not exists anymore"
        elif pid_changed:
            result["event"] = "This Process restart, pid have changed"
        item["last_notify"] = time_stamp

        bitmap.append(result)
        return

def check_related_process(param_dict):
    will_send = False

    global myip

    role = Role(myip)

    hit_result = []
    for item in RELATED_PROCESS:
        name = item["name"]
        p_type = item["p_type"]
        old_pid = item["pid_num"]
        pidfile = item["pid_file"]

        try:
            hit = False
            pid_changed = False
            pid_not_exist = False
            if p_type == 2 and role.get(GW) != RoleState.ENABLED:
                continue
            if p_type == 3 and role.get(RRS) != RoleState.ENABLED:
                continue

            raw = ""
            if p_type == 0:
                raw = do_cmd("pidof {} |tr -d '\n' ".format(name))
            else:
                raw = do_cmd("pidof python |tr -d '\n' ")
            logger.debug("pidof {} is {}".format(name, raw))

            if os.path.isfile(pidfile):
                new_pid = int(readfile(pidfile))
                logger.debug("new_pid in pid file is {}".format(new_pid))

                raw_array = raw.split(" ")

                if str(new_pid) not in raw_array:
                    hit = True
                    pid_not_exist = True
                else:
                    if old_pid != 0 and new_pid != old_pid:
                        hit = True
                        pid_changed = True

                    item["pid_num"] = new_pid
            else:
                logger.info("{} pid file is not exists".format(name))
                hit = True
                pid_not_exist = True
        except Exception as e:
            logger.exception("{} may not exists".format(name))
            hit = True
            item["pid_num"] = 0
            pid_not_exist = True

        if hit:
            update_hit_result(hit_result,pid_not_exist, pid_changed, item)


    logger.debug("hit_result {}".format(hit_result))


    if len(hit_result):
        will_send = True

    HIT_LOG = "Some Process not exists {}".format(hit_result)
    MISS_LOG = "Check Process OK"
    MAIL_TITLE = "Some Process not exists".format(name)
    MAIL_CONTENT = "{}".format(hit_result)
    check_post_process(will_send, param_dict, HIT_LOG, MISS_LOG, MAIL_TITLE, MAIL_CONTENT)


##################################################################################################
def check_osd_omap_size(param_dict):
    will_send = False
    
    raw = do_cmd("du -sm /data/osd.*/current/omap")
    buf = StringIO.StringIO(raw)

    line = buf.readline()
    line_array = []
    while line :
        logger.debug("{}".format(line))
        line_array = line.split()
        if int(line_array[0]) > notifications.OSD_OMAP_SPACE_THRESHOLD:
            will_send = True
            break
        line = buf.readline()

    HIT_LOG = "OSD LevelDB {} is too big {} MB".format(line_array[1],line_array[0])
    MISS_LOG = "Check OSD LevelDB size done, OK"
    MAIL_TITLE = "OSD LevelDB is too Huge"
    MAIL_CONTENT = "Please check this OSD's LevelDB:\n   {}".format(line)

    return check_post_process(will_send, param_dict, HIT_LOG, MISS_LOG, MAIL_TITLE, MAIL_CONTENT)
##################################################################################################
current_osd_pid_set = {}
def check_osd_down(param_dict):
    will_send = False

    raw = do_cmd("pidof ceph-osd |tr -d '\n'")
    pid_array = raw.split(' ')

    new_osd_pid_set = set(pid_array) 

    global current_osd_pid_set
    if len(current_osd_pid_set) == 0:
        current_osd_pid_set = new_osd_pid_set 
        return 

    dead_set = current_osd_pid_set - new_osd_pid_set
    new_set  = new_osd_pid_set - current_osd_pid_set

    if len(dead_set) != 0 :
        will_send = True
        current_osd_pid_set = new_osd_pid_set

    HIT_LOG="Some OSD dead since last check {}, {} are recently started OSD".format(dead_set, new_set)
    MISS_LOG="NO OSD down since last check, OK"
    MAIL_TITLE="Some OSD down"
    MAIL_CONTENT="OSD whose pid in {} Down, and these OSD ({}) are recently started OSD".format(dead_set, new_set)

    return check_post_process(will_send, param_dict, HIT_LOG, MISS_LOG, MAIL_TITLE, MAIL_CONTENT)


########################################################################
def check_ctdb_status(param_dict):
    dry_run = check_pre_process(param_dict)

    ezfs_agent_exception = False
    ctdb_exception = False

    global myip
    ctdb_status_json = kvstore.get('ctdb_status_{}'.format(myip), force=True)
    if ctdb_status_json:
        ctdb_status = json.loads(ctdb_status_json)
        if time.time() - float(ctdb_status['timestamp']) > 60:
            ezfs_agent_exception = True 
        elif ctdb_status['state'] not in ('OK', 'PARTIALLYONLINE'):
            ctdb_exception = True 
        else:
            pass

    if ezfs_agent_exception or ctdb_exception:
        if(ezfs_agent_exception):
            logger.error("Something wrong with ezfs-agent,please check")
        else:
            logger.error("Something wrong with CTDB,please check")

        if dry_run:
            pass
        else:
            if ezfs_agent_exception:
                ret = send_alert_mail("ezfs-agent Abnormal","please check ezfs-agent")
            else:
                ret = send_alert_mail("CTDB abnormal", "")

            if ret is True:
                time_stamp = time.time()
                param_dict['last_notify'] = time_stamp
            else:
                logger.error("send alert mail failed")
    else:
        logger.info("CTDB status is OK")

######################################################################################################
def check_mds_status(param_dict):
    will_send = False
   
    global myip
    role = Role(myip)
    if role.get(GW) != RoleState.ENABLED:
        logger.info("GW is not enable in this storage node, skip MDS check")
        return 

    found = False
    mdsmap = get_mdsmap()
    for info in mdsmap['info'].itervalues():
        ip,_ = info['addr'].split(':')
        if ip == myip:
            found = True
            up, state = info['state'].split(':')
            if up != 'up':
                will_send = True
                break
        else:
            continue

    if found is False:
        will_send = True

    HIT_LOG="MDS status is not up in mdsmap"
    MISS_LOG="MDS status is OK"
    MAIL_TITLE="MDS status Exception"
    MAIL_CONTENT="Please check ceph-mds process and ezs3-agent process"

    return check_post_process(will_send, param_dict, HIT_LOG, MISS_LOG, MAIL_TITLE, MAIL_CONTENT)
        

def check_interval(param_dict):
    if(param_dict is None):
        return False

    last_execute = param_dict['last_check']
    check_frequency = (param_dict['check_frequency'])*60
    
    last_notify = (param_dict['last_notify'])
    notify_frequency = (param_dict['notify_frequency'])*60

    logger.debug("last_check  {} check_frequency {}".format(last_execute, check_frequency))
    logger.debug("last_notify {} check_frequency {}".format(last_notify,  notify_frequency))
    

    time_stamp = time.time()

    if (last_notify + notify_frequency > time_stamp + 1800):
        check_frequency = max(check_frequency, 20*60)

    if time_stamp - last_execute < 0 :
        return True
    elif time_stamp - last_execute >= (check_frequency - 1):
        return True
    else:
        return False


MONITOR_ITEMS = [
        {
           'item_name':'check_process_num', 'cluster_wise':False,'check_frequency':5,'last_check':0,
           'notify_frequency':1440, 'last_notify': 0, 'processor': check_process_num
        },        
        {
           'item_name':'High-Mem cost Process','cluster_wise':False, 'check_frequency':2, 'last_check':0,
           'notify_frequency':1440, 'last_notify': 0, 'processor': check_high_mem_process
        },        
        
        {
           'item_name':'System loadavg','cluster_wise':False, 'check_frequency':2, 'last_check':0,
           'notify_frequency':120, 'last_notify': 0, 'processor': check_loadavg
        },        
        {
           'item_name':'System Free Memory','cluster_wise':False, 'check_frequency':2, 'last_check':0,
           'notify_frequency':1440, 'last_notify': 0, 'processor': check_free_memory
        },        
        {
           'item_name':'check OS FileSystem Read only','cluster_wise':False, 'check_frequency':2, 'last_check':0,
           'notify_frequency':1440, 'last_notify': 0, 'processor': check_readonly_os_partition
        },        
        {
           'item_name':'check OS partition usage','cluster_wise':False, 'check_frequency':2, 'last_check':0,
           'notify_frequency':1440, 'last_notify': 0, 'processor': check_os_partition_usage
        },        
        {
           'item_name':'check related process','cluster_wise':False, 'check_frequency':2, 'last_check':0,
           'notify_frequency':2, 'last_notify': 0, 'processor': check_related_process
        },        
        {
           'item_name':'check osd omap size','cluster_wise':False, 'check_frequency':2, 'last_check':0,
           'notify_frequency':1440, 'last_notify': 0, 'processor': check_osd_omap_size
        },        
        {
           'item_name':'check osd down','cluster_wise':False, 'check_frequency':2, 'last_check':0,
           'notify_frequency':4, 'last_notify': 0, 'processor': check_osd_down
        },        
        {
           'item_name':'check CTDB status','cluster_wise':False, 'check_frequency':2, 'last_check':0,
           'notify_frequency':1440, 'last_notify': 0, 'processor': check_ctdb_status
        },        
        {
           'item_name':'check MDS status','cluster_wise':False, 'check_frequency':2, 'last_check':0,
           'notify_frequency':1440, 'last_notify': 0, 'processor': check_mds_status
        },        

]

class SystemNotificationManager(Daemon):
    def __init__(self,pid_file):
        Daemon.__init__(
                    self,
                    pid_file,
                    stdout = "/var/log/systen_notification.out",
                    stderr = "/var/log/system_notification.err"
                )
        self._ceph_conf = Ezs3CephConfig()
        # suppose storage IP will not change
        self._storage_ip = get_interface_ipv4(self._ceph_conf.get_storage_interface())

        global MONITOR_ITEMS
        self._processors = {}
        for p in MONITOR_ITEMS:
            self._processors[p['item_name']] = p

    def run(self):
        logger.info("enter run")

        while self.is_daemon_running(SYSTEM_NOTIFICATION_CHECK_INTERVAL):
            cluster_mgr = ClusterManager()
            is_monitor_leader = cluster_mgr.is_mon_leader(self._storage_ip, timeout=10)

            items = self._processors.keys()

            for item in items:
                # judge can we skip this item this loop
                do_now = check_interval(self._processors[item])
                if do_now is False:
                    continue

                if self._processors[item]['cluster_wise']:
                    if is_monitor_leader:
                        try:
                            process_result = self._processors[item]['processor'](self._processors[item])
                        except Exception:
                            logger.exception("Run {} failed".format(item))
                    else:
                        continue
                else:
                    try:
                        process_result = self._processors[item]['processor'](self._processors[item])
                    except Exception:
                        logger.exception("Run {} failed".format(item))

def main(argv=None):
    daemon = SystemNotificationManager(SYS_NOTIFICATION_MGR_PIDFILE)
    if len(sys.argv) == 2:
        if 'start' == sys.argv[1]:
            daemon.start()
        elif 'stop' == sys.argv[1]:
            daemon.stop()
        elif 'restart' == sys.argv[1]:
            daemon.restart()
        else:
            print "Unknown command"
            sys.exit(2)
        sys.exit(0)
    else:
        print "usage: %s start|stop|restart" % sys.argv[0]
        sys.exit(2)

if __name__ == "__main__":
    sys.exit(main())
