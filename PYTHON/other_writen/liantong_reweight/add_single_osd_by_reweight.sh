#!/bin/bash

IFS=$'\n\t'

LOG=/var/log/import-osd.log
weight_value=$(ceph osd tree |grep $1 |tail -n 1  >&1 |awk '{print $2}')

if [ "$#" -lt 2 ]
then
    echo "Usage import-osd.sh target_osd target_value step"
    echo "e.g.  import-osd.sh osd.41 14"
    echo "e.g.  import-osd.sh osd.41 14 0.2"
    exit 1
fi

target_osd=$1
target_value=$2
step=0.2

if [ "$#" -eq 3 ]
then
    step=$3
    if [ `echo "$step > 0.8" |bc`  -eq 1 ]
    then
       echo $(date) "step is bigger than 0.8 , use 0.8 instead" >>$LOG
       step=0.8
    fi
fi


while true
do 
    unstable_pg_num=$(ceph health detail |grep "^pg" |grep -v current |grep acting |wc -l)
    ret=$?
    if [ $ret -ne 0 ];
    then
       sleep 30
       echo $(date) "ceph health detail execute failed" >>$LOG
       continue
    fi

    if [ $unstable_pg_num -eq 0  ]
    then
        if [ `echo "$weight_value >= $target_value" |bc` -eq 1 ];
        then
            echo $(date) "current weight $weight_value  target value $target_value , DONE and EXIT" >>$LOG
            exit 0
        fi
        new_value=$(echo $weight_value+$step |bc)
        if [ `echo "$new_value > $target_value" |bc ` -eq 1 ];
        then
           new_value=$target_value
        fi

        echo  $(date) "i will execute  ceph osd crush reweight $target_osd from $weight_value to $new_value "  >> $LOG
        ceph osd crush reweight $target_osd $new_value
        weight_value=$new_value
        sleep 20
    else
        echo $(date) "$unstable_pg_num PGs not active+clean" >>$LOG
        sleep 60
    fi
done
