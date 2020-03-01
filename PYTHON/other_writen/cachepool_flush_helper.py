#!/usr/bin/env python

import os
import sys
import time
import logging
import json
from copy import deepcopy
import ezs3.utils as utils
from ezs3.daemon import Daemon
from ezs3.log import EZLog
from ezs3.config import Ezs3CephConfig
from ezs3.cluster import ClusterManager
from threading import Thread
from ezs3.command import do_cmd

EZLog.init_handler(logging.INFO, "/var/log/ezcloudstor/cachepool_flush_helper.log")
logger = EZLog.get_logger(__name__)
CACHEPOOL_FLUSH_HELPER_PIDFILE="/var/run/cachepool_flush_helper"
CACHEPOOL_FLUSH_HELPER_INTERVAL = 20

OBJECT_NUM_FLUSH_ONE_TIME = 4
SLOW_FLUSH_THRESHOLD = 3
REASONABLE_WATERMARK_RATIO=0.75
REASONABLE_WATERMARK_HIGH_RATIO=0.85
MAX_OBJECT_INCREASE_RATIO_ALLOWED = 0.0005
MAX_NUMBER_OF_WORKER = 50

OBJECT_SIZE = 4*1024*1024

def process_one_pg(target_pool_name, target_pool_id,  pg_idx, low_thresh, high_thresh):
    pg_idx_str = hex(pg_idx)[2:]
    logger.debug("enter process one pg {}  {}.{} target {}"
                 .format(target_pool_name,target_pool_id, pg_idx_str, high_thresh))

    try:
        pg_info_str = do_cmd("ceph pg {}.{} query"
                             .format(target_pool_id, pg_idx_str),
                             timeout=10 )
    except Exception as e:
        logger.error("failed to get pg info {}".format(str(e)))
        logger.warning("Quit process PG {}.{}".format(target_pool_id, pg_idx_str))
        return 

    pg_info = json.loads(pg_info_str)

    num_objs = int(pg_info["info"]["stats"]["stat_sum"]["num_objects"])
    
    if num_objs < low_thresh:
        logger.debug("skip pg {}.{}  ({})".format(target_pool_id, pg_idx_str, num_objs))
        return 

    flush_number = 16
    if high_thresh < 256:
        flush_number = int(high_thresh/16)
   
    if flush_number < 2:
        flush_number = 2

    # sleep interval changed from [50ms, 200ms]
    if num_objs < high_thresh:
        sleep_interval = int(50 + 150.0*(high_thresh-num_objs)/(high_thresh-low_thresh))
        sleep_interval = float(sleep_interval)/1000
    else:
        sleep_interval = 0.05
   
    try:
        obj_list_str = do_cmd("rados ls {}.{} {} -p {} "
                               .format(target_pool_id, pg_idx_str, 
                                       flush_number, target_pool_name
                                      ),
                               timeout=10
                             )
    except Exception as e:
        logger.error("failed to get object list by rados ls for PG {}.{}"
                     .format(target_pool_id, pg_idx_str))
        logger.warning("Quit process PG {}.{}".format(target_pool_id, pg_idx_str))
        return 

    obj_list = obj_list_str.split()

    index = 0
    begin_timestamp = time.time()
    for obj in obj_list:
        try: 
            if obj.startswith("rbd_header"):
                continue

            logger.debug("flush {} {}.{}  {}"
                          .format(target_pool_name, target_pool_id, pg_idx_str, obj))  
            do_cmd("rados -p {} cache-try-flush {}"
                    .format(target_pool_name, obj), 
                    timeout=10)
            do_cmd("rados -p {} cache-evict {}"
                    .format(target_pool_name, obj),
                    timeout=10)
        except Exception as e:
            logger.info("something error happed when flush {} {}.{} {} {}"
                        .format(target_pool_name,target_pool_id, pg_idx_str, obj, e))

        index = index+1
        time.sleep(sleep_interval)
        if index % OBJECT_NUM_FLUSH_ONE_TIME == 0:
            end_timestamp = time.time()
            process_time_avg = (end_timestamp - begin_timestamp)/OBJECT_NUM_FLUSH_ONE_TIME
            begin_timestamp = end_timestamp

            # if flush one object cost 3 second by average, stop flush this pg
            if  process_time_avg >= SLOW_FLUSH_THRESHOLD:
                break

def flush_worker(idx, pool):
    logger.debug("enter flush_worker")

    logger.debug("idx {} pool {}".format(idx,pool))
    pg_idx = idx
    peer_num = pool["number_of_worker"]
    total_pg = int(pool["pg_num"])
    target_pool_name = pool["pool_name"]
    target_pool_id = pool["pool_id"]

    low_thresh =  int(pool["full_ratio_objects"]*REASONABLE_WATERMARK_RATIO/total_pg)
    high_thresh = int(pool["full_ratio_objects"]*REASONABLE_WATERMARK_HIGH_RATIO/total_pg)

    if high_thresh == low_thresh:
        high_thresh = low_thresh + 1

    while pg_idx < total_pg:
        try:
            logger.debug("flush worker begin  process {}.{}".format(target_pool_id, hex(pg_idx)[2:]))
            process_one_pg(target_pool_name, target_pool_id, pg_idx, low_thresh, high_thresh)
            logger.debug("flush worker finish process {}.{}".format(target_pool_id, hex(pg_idx)[2:]))
            pg_idx  = pg_idx + peer_num
        except Exception as e:
            logger.error("process one pg({}.{} ) failed {}".format(target_pool_id, hex(pg_idx)[2:], e))
    return 0

class CachePoolFlushHelper(Daemon):
    def __init__(self,pid_file):
        Daemon.__init__(
                    self,
                    pid_file,
                    stdout = "/var/log/cachepool_flush_help.out",
                    stderr = "/var/log/cachepool_flush_helper.err"
                )
        self._ceph_conf = Ezs3CephConfig()
        self.myip = utils.get_interface_ipv4(
            self._ceph_conf.get_storage_interface()
        )   

        self.cachepools_last = []
        self.cachepools = []


    def update_cachepools_info(self):
        cluster_mgr = ClusterManager()
        cachepools = cluster_mgr.list_cache_pools()

        self.cachepools_last = deepcopy(self.cachepools)
        self.cachepools = []
        current = {}
        for pool in cachepools:
            current["pool_name"] = pool

            cmd_str = "ceph osd pool get {} pg_num --format=json".format(pool)
            json_str =  do_cmd(cmd_str, timeout=10)
            json_result = json.loads(json_str)
            current["pool_id"] = json_result["pool_id"]
            current["pg_num"] = int(json_result["pg_num"])

            cmd_str = "ceph osd pool get {} target_max_bytes --format=json".format(pool)
            json_str =  do_cmd(cmd_str, timeout=10)
            json_result = json.loads(json_str)
            current["target_max_bytes"] = int(json_result["target_max_bytes"])
            current["max_objects"] = int(current["target_max_bytes"]/OBJECT_SIZE)

            cmd_str = "ceph osd pool get {} cache_target_full_ratio --format=json".format(pool)
            json_str =  do_cmd(cmd_str, timeout=10)
            json_result = json.loads(json_str)
            current["full_ratio"] = float(json_result["cache_target_full_ratio"])
            current["full_ratio_objects"] = int(current["max_objects"] * current["full_ratio"])

         
            cmd_str = "rados df -p {} --format=json".format(pool)
            json_str = do_cmd(cmd_str, timeout=10)
            rados_df = json.loads(json_str)
            current["num_objects"] = int(rados_df["pools"][0]["categories"][0]["num_objects"])
            
            found_in_last = False
            num_objects_last = 0

            for pool_old in self.cachepools_last:
                if pool_old["pool_name"] == pool:
                    found_in_last = True
                    num_objects_last = pool_old["num_objects"]
                    number_of_worker_last = pool_old["number_of_worker"]

            # calc number_of_worker        
            if not found_in_last:
                current["number_of_worker"] = 4
            elif current["num_objects"] > current["full_ratio_objects"]*REASONABLE_WATERMARK_RATIO:
                if current["num_objects"] - num_objects_last < current["full_ratio_objects"]*MAX_OBJECT_INCREASE_RATIO_ALLOWED:
                    current["number_of_worker"] = number_of_worker_last
                elif current["num_objects"] < current["full_ratio_objects"]*REASONABLE_WATERMARK_HIGH_RATIO: 
                    current["number_of_worker"] = number_of_worker_last + 1
                else:
                    current["number_of_worker"] = number_of_worker_last + 2

                if current["number_of_worker"] != number_of_worker_last:
                    logger.info("Pool {} increase worker number to {}".format(pool, current["number_of_worker"]))
            else:
                current["number_of_worker"] = number_of_worker_last

            if current["number_of_worker"] > MAX_NUMBER_OF_WORKER:
                current["number_of_worker"] = MAX_NUMBER_OF_WORKER


            # skip this loop or not
            if current["num_objects"] > current["full_ratio_objects"]*REASONABLE_WATERMARK_RATIO:
                current["skip_this_loop"] = False
            else:
                current["skip_this_loop"] = True

            self.cachepools.append(deepcopy(current))

        logger.info("cachepools {}".format(self.cachepools))
               

    def single_loop(self):
        logger.info("enter single loop")
        
        self.update_cachepools_info()

        threads = []
        for pool in self.cachepools:
            if pool["skip_this_loop"] == True:
                logger.info("Skip this loop for POOL {}".format(pool["pool_name"]))
                continue
            for i in range(pool["number_of_worker"]):
                t = Thread(target = flush_worker,args=(i, pool))
                t.daemon = True
                threads.append(t)
                t.start()

        for t in threads:
            t.join()
        

    def run(self):
        logger.info("enter run")

        while self.is_daemon_running(CACHEPOOL_FLUSH_HELPER_INTERVAL):
            cluster_mgr = ClusterManager()
            is_leader = cluster_mgr.is_mon_leader(self.myip, timeout=10)
            if is_leader:
                self.single_loop()

            logger.info("finish one loop")



def main(argv=None):
    daemon = CachePoolFlushHelper(CACHEPOOL_FLUSH_HELPER_PIDFILE)
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

