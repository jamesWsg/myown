
import sys
from ezs3.command import do_cmd
import commands
from copy import deepcopy
import json
import logging
import traceback
from ezs3 import storage
from ezs3.log import EZLog
from ezs3.remote import ASYNC_MODE
from ezs3.cluster import ClusterManager, Role, RoleState, GW


EZLog.init_handler(logging.DEBUG, "/var/log/ezcloudstor/reformat-osd.log")
logger = EZLog.get_logger("reformat-osd")

def check_cluster_health():
    script='ceph health detail |grep "^pg" |grep -v current |grep acting |wc -l'
    unstable_pg_num=commands.getoutput(script)
    logger.debug("excute the ceph health,unstable_pg_num is {}".format(unstable_pg_num))
    if int(unstable_pg_num) is 0:
        logger.debug("unstable_pg_num is {},cluster should be health".format(unstable_pg_num))
        return True
    else:
        logger.debug("unstable_pg_num is {},should not be 0".format(unstable_pg_num))
        return False

def have_zero_weight_osd(cm):
    result=False
    for osd in cm.get_osds(15)[1]:
        osd_name, crush_weight=cm.get_osd_crush_weight(int(osd.id))
        if crush_weight==0:
            result=True
            return result,osd.id,osd.ip
            break

            return result,None,None

def get_osd_name_by_id(osd_id):
    cmd_str = "cat /etc/ezs3/storage.conf"
    output = do_cmd(cmd_str)
    storage_conf = json.loads(output)
    for item in storage_conf:
        if item["osd_id"]==osd_id:
            return item["name"]



def choose_osd_with_ext4_erro():
    #cmd_str = "python /root/cluster_check"
    #output = do_cmd(cmd_str, Force=True)
    
    #for test
    output=do_cmd("cat /root/json.txt")

    corrupt_osds = []

    total_result = json.loads(output)
    ext4_result = total_result["EXT4-fs error"]["bad_part"]

    for item in ext4_result:
        ip = item['IP']
    for osd in item['corrupt_osds']:
        current = {}
        current["err_num"] = osd["error_num"]
        current["osd_id"]  = osd["osd"]
        current["ip"] = ip

        corrupt_osds.append(deepcopy(current))
    #logs = sorted(logs, key = lambda item : item['log_time'], reverse = True)
    corrupt_osds = sorted(corrupt_osds, key = lambda item: item['err_num'], reverse = True)
    
    logger.debug("all osd have ext4 erro : {}".format(corrupt_osds))
    osd = corrupt_osds[0]["osd_id"]   #osd.53
    logger.debug("choose the osd have max erro count: {}".format(osd))
    #return osd

    #for test
    return '1'



if __name__ == "__main__":
    cm = ClusterManager()
    #nodes = cluster.list_nodes()


    if check_cluster_health():
        try:
            result,osd_id,osd_ip=have_zero_weight_osd(cm)
        except Exception:
            logger.debug("some err happen when call fuction have_zero_weight_osd:{}".format(traceback.format_exc()))
        if result==True:
            osd_name=get_osd_name_by_id(osd_id)
            try:
                host=osd_ip
                #names is a list,so should change osd_name to a list,
                names=[osd_name]
                logger.debug("will begin reformat osd {} in ip {}".format(osd_id,osd_ip))
                #storage.reformat_storage_volume(names,_host=host,_async=ASYNC_MODE.NO_WAIT)

                ##sleep a while,then check the osd is up,then reweight to total

            except Exception:
                print(traceback.format_exc())

        else:
            #choose osd to reweiht to 0
            target_osd=choose_osd_with_ext4_erro()

            logger.debug("will begin reweight  {}".format(target_osd))
            #need to check target_osd
            #do_cmd("ceph osd crush reweight osd.{} 0".format(target_osd))

