
from Queue import Queue
import json
import sys
import logging
from ezs3.log import EZLog
from ezs3.cluster import ClusterManager
from ezs3.command import do_cmd

import ezs3.remote as remote
import commands

def get_osd_list(ip):
    cmd="df -h |grep \"/data/osd\" |awk '{print $6}'"
    result_list=do_cmd("ssh {} {}".format(ip,cmd)).split('\n')

    # the result_list tail has space,need to remove,
    result_list.remove('')    
    return result_list
        
    
def add_node(ip,target_weight):
    osd_list=get_osd_list(ip)
    
    for osd in osd_list:
        target_osd=osd[6:]
        script='bash /root/wsg/add_single_osd_by_reweight.sh {} {}'.format(target_osd,target_weight)
        shell_result=commands.getoutput(script)
        print shell_result


if __name__ == '__main__':
    ip_list=['172.17.13.208','172.17.13.210']

    for ip in ip_list:
        add_node(ip,15)


