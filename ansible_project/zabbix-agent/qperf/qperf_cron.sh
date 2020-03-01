#!/bin/bash
##################################
# Zabbix monitoring script
#
# Info:
#  - cron job to gather qperf data
#  - can not do real time as qperf data gathering will exceed 
#    Zabbix agent timeout
##################################
# Contact:
##################################
# ChangeLog:
#  20181211	VV	initial creation
##################################

LOG=/var/log/zabbix_qperf.log

# check ip list,need to prepare

IP_LIST_FILE=/usr/local/zabbix-agent-ops/bin/qperf_check_ip_list


# source data 
DEST_DATA_DIR=/usr/local/zabbix-agent-ops/var/
#
# gather data in temp file first, then move to final location
# it avoids zabbix-agent to gather data from a half written source file
#
#
################################3
## result
# qperf_result_172.17.73.243_tmp

#echo "qperf_cron_log" >>$LOG
#pwd >>$LOG
#cd ${DEST_DATA_DIR}



cat $IP_LIST_FILE |xargs -I{} -P 1 bash -c "/usr/local/bin/qperf {} tcp_bw tcp_lat >${DEST_DATA_DIR}qperf_result_{}_tmp"


###################   for: also work,stay here for reference
#ip_list=`cat $IP_LIST_FILE`
#for ip in $ip_list;do
#  /usr/local/bin/qperf $ip tcp_bw tcp_lat >${DEST_DATA_DIR}qperf_result_${ip}_tmp
#done



#generate the result
cat $IP_LIST_FILE |xargs -I{} -P 1 bash -c "cp ${DEST_DATA_DIR}qperf_result_{}_tmp ${DEST_DATA_DIR}qperf_result_{}"
