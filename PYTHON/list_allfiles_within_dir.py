
#!/usr/bin/env python
# -*- coding:UTF-8 -*-

import os
import sys

from ezs3.log import EZLog

from ezs3.command import do_cmd




def get_all_files_with_path(rootdir):

    files_with_path_list =[]    
    for root, dirs, files in os.walk(rootdir):
        for filename in files:
            #print filename
            files_with_path_list.append(os.path.join(root, filename))
            print files_with_path_list

    return files_with_path_list






def save_files_to_file(rootdir,save_to_file):

    tmp_list=get_all_files_with_path(rootdir)
    with open (save_to_file,'w') as thefile:
        for line in tmp_list:
            thefile.write(line+'\n')


def read_all_files(save_to_file,parallel):
    for i in xrange(200000):

        cmd="cat {0} |xargs -I [] -P {1} dd if=[] of=/dev/null bs=1M".format(save_to_file,parallel)   
        print cmd
        do_cmd(cmd)

def main():

    rootdir = '/vol/folder-new1/'
    save_to_file='all_files_with_path'
    #get_all_files_with_path(rootdir)

    save_files_to_file(rootdir,save_to_file)
    read_all_files(save_to_file,5)

if __name__ == '__main__':
    sys.exit(main())
