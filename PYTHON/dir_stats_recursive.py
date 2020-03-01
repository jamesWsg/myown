
#!/usr/bin/env python
# -*- coding:UTF-8 -*-

import os
import sys
import operator
#from ezs3.log import EZLog

from ezs3.command import do_cmd
import logging

logging.basicConfig(filename='/var/log/ezcloudstor/dir_stats.log',format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S',level=logging.INFO)


def get_num_files_in_dir(rootdir):
    if isinstance(rootdir, str):
        try:
            rootdir = rootdir.decode('utf8')
        except UnicodeDecodeError:
            rootdir = rootdir.decode('gbk')

    cmd=u'getfattr -d -m - {}|grep "ceph.dir.files" |uniq -c'.format(rootdir)
    ## the cmd tail add uniq -c because the output maybe have two lines

    #print cmd.encode('utf8')
    output=do_cmd(cmd).split('=')[1]
    return output.strip('\n').strip('"')

def get_all_dirs(rootdir):

    #files_with_path_list =[]
    ## result is dic,key is path,value is the num files the path have
    #global var: dir_files_num={}

    for root, dirs, files in os.walk(rootdir):
        for each_dir in dirs:
            dest_dir=os.path.join(root, each_dir)
            #print 'prepare do get nums for {}'.format(dest_dir)
            #print type(dest_dir)

            try:
                result[dest_dir]=int(get_num_files_in_dir(dest_dir))

            except Exception as e:
                logging.error("catch exception:{}, \n,dest_dir is {}".format(str(e),dest_dir))
                continue



            #print filename
            #files_with_path_list.append(os.path.join(root, filename))
            #print files_with_path_list


def main():

    rootdir = '/var/share/ezfs/shareroot/share/shengguo/work_bak'
    save_to_file='all_files_with_path'
    global result
    result={}
    
    get_all_dirs(rootdir)
    #print result
    logging.info("the raw result is {}\n".format(result))
    #print 'sorted resul'

    #the sorted_result type is not dict,as fllowing
    #[('/var/share/ezfs/shareroot/share/shengguo/iso_squashfs_initrd/squashfs-root/var/lib/dpkg/info', 893), ('/var/share/ezfs/shareroot/share/shengguo/iso_squashfs_initrd/squashfs-root/usr/share/man/man1', 402)]
    sort_result=sorted(result.items(), key=lambda x: x[1], reverse=True)

    logging.info("the sorted result is {}\n".format(sort_result))
    #print sort_result

    #when result have chinese,can not display,need decode


    ## print top5
    i=0
    result_chinese_decode={}
    for each_dir,dir_num in sort_result:
        if i < 5:

            result_chinese_decode[each_dir.decode('utf-8')]=dir_num
            #only can print chinese in this,not know why the fllowing print can not print chinese
            print each_dir,dir_num
            i=i+1

        else:
            break

    
    print "top five dir \n {}".format(result_chinese_decode)
    logging.info("#################\n the decoded result:{}".format(result_chinese_decode))





if __name__ == '__main__':
    sys.exit(main())
