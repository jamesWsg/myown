#!/bin/bash


#usage:if you want run muliple cmd on each node,run as following
#bash do_cmd_allnode.sh "hostname;who -b"

ceph mon dump |grep ':6789' |awk '{print $2}' |awk -F: '{print $1}' >/root/allnode  


echo "parameter "$@


for i in `cat /root/allnode`; do 
  echo 'do cmd on '$i
  ssh $i $@

done


