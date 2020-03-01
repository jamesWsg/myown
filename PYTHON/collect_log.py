import os
import sys
import json
import time
import traceback

from copy import deepcopy
from datetime import datetime, timedelta
from ezs3.command import do_cmd
from ezs3 import kvstore
from ezs3.central_log import CentralLogManager
import logging
from ezs3.log import EZLog
from ezs3.cluster import ClusterManager, Role, RoleState, GW
from optparse import OptionParser
import ezmonitor
from ezs3.utils import list_host_nics
from ezmonitor.cluster_data_collector import ClusterDataCollector, CF

## log initial put in main ,for use PATH parameter
#EZLog.init_handler(logging.INFO, "/root/collect_log.log")
#logger = EZLog.get_logger("collect_log")

now = datetime.now().strftime('%m%d_%H%M')
log_collect_dir='/root/log_collect_dir_{}/'.format(now)
collect_log='{}collect.log'.format(log_collect_dir)
EZLog.init_handler(logging.INFO, collect_log)
logger = EZLog.get_logger(collect_log)


def collect_history_data(rrd_name_list,LOG_DIR):

    cdc = ClusterDataCollector()
    
    end=int(time.time())

    #24 hours:fetch_range=86400; 7 day:fetch_range=604800;  30 days:fetch_range=2592000

    fetch_range=2592000
    start = end - fetch_range
    #resp = cdc.fetch_last('cluster', cf=CF.LAST, resolution=3600)
#    resp = cdc.fetch('host_memory',cf=CF.LAST, resolution=3600, start=start, end=end)
#    print resp
    for rrd_name in rrd_name_list:
	    resp = cdc.fetch(rrd_name=rrd_name,cf=CF.LAST, resolution=60, start=start, end=end)
	    save_to_file=LOG_DIR+rrd_name+'.collect_data'
	    with open(save_to_file,'w') as f:
	        f.write(json.dumps(resp))
def collect_node_NIC(node):
    result={}
    try:
        if_info = list_host_nics(_host=node)

        ##debug print 'eth_name:{}\n eth_info:{}\n'.format(eth_name,eth_info)
        ## debug print 'eth_name:{}\n eth_info_role:{}\n'.format(eth_name,eth_info['role'])
        for eth_name,eth_info in if_info.items():           
            if 'public' in eth_info['role']:
                result['public_interface']=eth_name
            elif 'storage' in eth_info['role']:
                result['storage_interface']=eth_name
    except Exception as e:
        logger.error("catch exception:{}".format(str(e)))
        logger.error("call trace:{}".format(traceback.format_exc()))

    print result 
    return result

def collect_node_info(LOG_DIR):
   print 'begin collect node info'
   result={}
   cluster = ClusterManager()
   nodes = cluster.list_nodes()
   ##debug print 'nodes {}'.format(nodes)
   for node in nodes:
       try:
           print 'node:{}'.format(node)
           #print 'if info {}\n\n'.format(if_info)  

           result[node]=collect_node_NIC(node)

       except Exception as e:
           logger.error("catch exception:{}".format(str(e)))
           logger.error("call trace:{}".format(traceback.format_exc()))
   save_to_file=LOG_DIR+'rrd_node_info'
   with open(save_to_file,'w') as f:
       f.write(json.dumps(result))

def collect_ctdb_log(nodes=None, detail=False):
    cmd_list=['ctdb ip','ctdb status','hostname','ip add','lscpu','free -g']
    if nodes is None:
        cluster = ClusterManager()
        nodes = cluster.list_nodes()

    for node in nodes:
        try:
            for cmd in cmd_list:
                raw = do_cmd("ssh {} {}".format(node,cmd))
                logger.info("begin do cmd: {} on node:{} \n{}".format(cmd,node,raw))
                
        except Exception as e:
                logger.error("catch exception:{}".format(str(e)))
                logger.error("call trace:{}".format(traceback.format_exc()))



def collect_iscsi_log(nodes=None, detail=False):
    cmd_list=['rbd showmapped','lsscsi','lsblk', 'df -h']
    print cmd_list
    if nodes is None:
        cluster = ClusterManager()
        nodes = cluster.list_nodes()

    for node in nodes:
        for cmd in cmd_list:
            print cmd
            logger.info("begin do cmd: {} on node:{} \n".format(cmd,node))
            raw = do_cmd("{}".format(cmd), _host=node)
            #if not isinstance(raw, unicode):
            raw = unicode(raw, 'utf-8', 'ignore')
            logger.info(u"begin do cmd: {} on node:{} \n {} \n".format(cmd,node,raw))




def collect_ceph_log(nodes=None, detail=False):
    cmd_list=['ceph -s','ceph health detail','ceph osd tree','ceph osd dump']
    if nodes is None:
        cluster = ClusterManager()
        nodes = cluster.list_nodes()

    for node in nodes:
        try:
            for cmd in cmd_list:
                raw = do_cmd("ssh {} {}".format(node,cmd))
                logger.info("begin do cmd: {} on node:{} \n{}".format(cmd,node,raw))
                
        except Exception as e:
                logger.error("catch exception:{}".format(str(e)))
                logger.error("call trace:{}".format(traceback.format_exc()))

def collect_raid_log(nodes=None, detail=False):
    cmd_list=[
              '/opt/MegaRAID/MegaCli/MegaCli64 ldinfo -lall -a0',
              '/opt/MegaRAID/MegaCli/MegaCli64 -ldinfo -lall -a0 |grep -Ei "state"',
	      '/opt/MegaRAID/MegaCli/MegaCli64 adpallinfo -a0 |grep -Ei "critical|Failed Disk"'
	     ]
    if nodes is None:
        cluster = ClusterManager()
        nodes = cluster.list_nodes()

    for node in nodes:
        try:
            for cmd in cmd_list:
                raw = do_cmd("ssh {} {}".format(node,cmd))
                logger.info("begin do cmd: {} on node:{} \n{}".format(cmd,node,raw))
                
        except Exception as e:
                logger.error("catch exception:{}".format(str(e)))
                logger.error("call trace:{}".format(traceback.format_exc()))


def tar_all_node_log(log_collect_dir,nodes=None):
    if nodes is None:
        cluster = ClusterManager()
        nodes = cluster.list_nodes()
    
	now = datetime.now().strftime('%m%d_%H:%M')
	#now_date, now_time = now.split(' ')

	log_collect_node=nodes[0]
	log_dir='{}tar_log'.format(log_collect_dir)
	cmd='mkdir -p {}'.format(log_dir)
	raw = do_cmd("ssh {} {}".format(log_collect_node,cmd))
	print log_collect_node,log_collect_dir

    for node in nodes:
        
        try:
	    dst_dir='/root/{}'.format(node)
            # clear the old data  
            cmd='rm -rf  {}'.format(dst_dir)
            raw = do_cmd("ssh {} {}".format(node,cmd))
	    print 'first,rm the old log dir '

            cmd='mkdir -p {}'.format(dst_dir)
            raw = do_cmd("ssh {} {}".format(node,cmd))
	    print cmd

	    #cp ceph log
	    cmd='cp -R /var/log/ceph/ {}'.format(dst_dir)
            raw = do_cmd("ssh {} {}".format(node,cmd))
	    logger.info("cmd:{},on node:{},result:{} \n".format(cmd,node,raw))
            
	    #cp sys log
	    cmd='cp  /var/log/syslog* {}'.format(dst_dir)
            raw = do_cmd("ssh {} {}".format(node,cmd))
	    logger.info("cmd:{},on node:{},result:{} \n".format(cmd,node,raw))
	    
            
	    #cp kern 
	    cmd='cp  /var/log/kern.log* {}'.format(dst_dir,dst_dir)
            raw = do_cmd("ssh {} {}".format(node,cmd))
	    logger.info("cmd:{},on node:{},result:{} \n".format(cmd,node,raw))
	    
	    #cp ctdb log
	    cmd='cp -R /var/log/ctdb/ {}'.format(dst_dir)
            raw = do_cmd("ssh {} {}".format(node,cmd))
	    logger.info("cmd:{},on node:{},result:{} \n".format(cmd,node,raw))

	    
	    
	    #scp node log to log_collect_node
	    cmd='scp -r {} {}:{} '.format(dst_dir,log_collect_node,log_dir)
	    raw = do_cmd("ssh {} {}".format(node,cmd))
	    logger.info("cmd:{},on node:{},result;{} \n".format(cmd,node,raw))

        except Exception as e:
                logger.error("catch exception:{}".format(str(e)))
                logger.error(traceback.format_exc())

    # tar the log
    cmd='tar -czvf {}tar_log.tgz {}'.format(log_collect_dir,log_dir)
    raw = do_cmd("ssh {} {}".format(log_collect_node,cmd))
    print 'complete tar the log'

    # after tar,rm the raw log,
    cmd='rm -rf  {}'.format(log_dir)
    raw = do_cmd("ssh {} {}".format(log_collect_node,cmd))
    print 'clear the raw log,finish '

def collect_cluster_check_log(log_collect_dir):

    raw = do_cmd("cluster_check -d >{}clustercheck.result.detail".format(log_collect_dir))
    logger.info("begin do cluster_check  \n{}".format(raw))


def main(argv=None):

    collect_ceph_log()
    collect_ctdb_log()
    collect_iscsi_log()
    collect_raid_log()

    
    # new add for collect the rrd data
    rrd_name_list=['cluster','host_memory','host_network_util','host_network_io','host_disk_util','host_cpu']
    ## host_disk_latency not in 6.1 , 6.3 include this

    collect_history_data(rrd_name_list,log_collect_dir)
    collect_node_info(log_collect_dir)
    collect_cluster_check_log(log_collect_dir)


    #if you need the log file,coment out the next function
    tar_all_node_log(log_collect_dir)

if __name__ == '__main__':
    sys.exit(main())




