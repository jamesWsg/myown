#!/bin/bash
##################################
# Zabbix monitoring script
#
#
# Info:
#  - vmstat data are gathered via cron job
##################################
# Contact:
##################################
# ChangeLog:
#  20100922	VV	initial creation
##################################

# Zabbix requested parameter
ZBX_REQ_DATA="$2"
ZBX_REQ_DATA_IP="$1"

# source data file
SOURCE_DATA=/usr/local/zabbix-agent-ops/var/qperf_result_${ZBX_REQ_DATA_IP}
LOG=/var/log/zabbix_qperf.log
#
# Error handling:
#  - need to be displayable in Zabbix (avoid NOT_SUPPORTED)
#  - items need to be of type "float" (allow negative + float)
#
ERROR_NO_DATA_FILE="-0.9900"
ERROR_OLD_DATA="-0.9901"
ERROR_WRONG_PARAM="-0.9902"
ERROR_MISSING_PARAM="-0.9903"

# No data file to read from
if [ ! -f "$SOURCE_DATA" ]; then
  echo $ERROR_NO_DATA_FILE
  exit 1
fi

# Missing device to get data from
if [ -z "$ZBX_REQ_DATA_IP" ]; then
  echo $ERROR_MISSING_PARAM
  exit 1
fi

#
# Old data handling:
#  - in case the cron can not update the data file
#  - in case the data are too old we want to notify the system
# Consider the data as non-valid if older than OLD_DATA minutes
#
OLD_DATA=5
if [ $(stat -c "%Y" $SOURCE_DATA) -lt $(date -d "now -$OLD_DATA min" "+%s" ) ]; then
  echo $ERROR_OLD_DATA
  exit 1
fi



process_tcp_bw()
{
  result=$(cat $SOURCE_DATA |grep bw |awk -F= '{print $2}')
  value=`echo $result |awk '{print $1}'`
  unit=`echo $result |awk '{print $2}'`

  if [[ ${unit} == 'MB/sec' ]];then
      #return $value
      echo $value
  elif [[ $unit == 'GB/sec' ]];then
      new_value=`echo $value*1024 |bc`
      echo $new_value
  else 
     echo "unexpect erro" >>$LOG
  fi
}


process_tcp_lat()
{
  result=$(cat $SOURCE_DATA |grep latency |awk -F= '{print $2}')
  value=`echo $result |awk '{print $1}'`
  unit=`echo $result |awk '{print $2}'`

  if [[ ${unit} == 'us' ]];then
      #return $value
      echo $value
  elif [[ $unit == 'ms' ]];then
      new_value=`echo $value*1000 |bc`
      echo $new_value
  else 
     echo "unexpect erro" >>$LOG
  fi
}

# 
# Grab data from SOURCE_DATA for key ZBX_REQ_DATA
#

# 2nd grab the data from the source file
case $ZBX_REQ_DATA in
  bw)     process_tcp_bw
          ;;
  lat)     process_tcp_lat
          ;;
  *) echo $ERROR_WRONG_PARAM; exit 1;;
esac

exit 0

