#/bin/bash

dest_ip=172.17.75.125
repeat_times=10
bin_tcpping='/usr/local/bin'
log=/var/log/tcpping.log

${bin_tcpping} -c -x ${repeat_times} ${dest_ip} |awk '{ print $0;sum += $3;} END {print "average = " sum/NR }' >${log}

cat ${log} |grep  

