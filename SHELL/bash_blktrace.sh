#!/bin/bash

##usage:
# bash bash_blktrace.sh sdb sdc 10

#$3 time

my_date=`date "+%H:%M:%s"`
result_dir=/root/blktrace_${my_date}_$1_$2


mkdir -p $result_dir

cd $result_dir

blktrace -d /dev/$1 /dev/$2 -w $3

blkparse -i $1 -d $result_dir/combine.$1 &

blkparse -i $2 -d $result_dir/combine.$2 &

wait

btt -i combine.$1 >$result_dir/result.$1
btt -i combine.$2 >$result_dir/result.$2


