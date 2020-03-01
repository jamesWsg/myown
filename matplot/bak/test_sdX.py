#!/usr/bin/env python 


import os
import time
import sys
import json
from copy import deepcopy
import  datetime
from optparse import OptionParser
import logging
import matplotlib.pyplot as plt
import matplotlib.dates as mdate
import numpy as np


logging.basicConfig(filename='report.log',format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S',level=logging.INFO)
logging.info('log begin.')

def process_cluster_data(filename):
    print('begin process cluster data')
    with open(filename,'r') as f:
        data = json.load(f)
    print('open rrd_data')
    plot_data=data['data']['cluster']
    item_time=plot_data[0]
    all_item_name=plot_data[1]
    all_item_data=plot_data[2]

    plot_time=convert_time_to_matplot(item_time)


    read_ops=[]
    write_ops=[]
    read_bytes=[]
    write_bytes=[]
    print(read_ops)
    for item_data in all_item_data:
        read_ops.append(item_data[0])
        write_ops.append(item_data[1])
        read_bytes.append(item_data[2])
        write_bytes.append(item_data[3])
    '''
    plot
    '''
    print(read_bytes)
    print(read_ops)

    fig, ax_arr = plt.subplots(2,sharex=True)

    #ax.plot(fds, read_ops, 'ro-')
    ax_arr[0].plot(plot_time, read_ops, 'palegreen',label='read_ops')
    ax_arr[0].plot(plot_time, write_ops, 'black',label='write_ops')

    ax_arr[0].xaxis_date()
    #fig.autofmt_xdate()
    xfmt = mdate.DateFormatter('%y-%m-%d %H:%M')
    ax_arr[0].xaxis.set_major_formatter(xfmt)
    
    ##

    ax_arr[1].plot(plot_time, read_bytes, 'palegreen',label='read_ops')
    ax_arr[1].plot(plot_time, write_bytes, 'black',label='write_ops')

    ax_arr[1].xaxis_date()
    ax_arr[1].xaxis.set_major_formatter(xfmt)
    
    leg = plt.legend(loc='upper right', ncol=2, shadow=True, fancybox=True)
    
    #plt.show()
    plt.savefig('cluster')
    plt.close()



def get_node_disks(node,all_nodes_disks):
    node_disks=list(filter(lambda x: node in x , all_nodes_disks))

    return node_disks


def process_all_node_disk_util(filename,nodes):
    print('begin process disk data')
    with open(filename,'r') as f:
        data = json.load(f)
    print('open rrd_data')
    
    all_node_data=data['data']

    all_nodes_disks=all_node_data.keys()
    
    ###begin plot
    plot_num=len(nodes)
    fig, ax_arr = plt.subplots(plot_num,sharex=True)

    xfmt = mdate.DateFormatter('%y-%m-%d %H:%M')


    print(plot_num)

    i=0
    # i is for plt.subplot

    for node in nodes:
        try:
            plot_disks_list=get_node_disks(node,all_nodes_disks)
            ## map each disk to a color
            ## assume the number of colors is enough,larger than the disks,otherwise will over flow
            color_list=['lightgreen','forestgreen','limegreen','darkgreen','green','lime','seagreen','mediumseagreen','springgreen']
            plot_disks = {}
            index=0
            for disk in plot_disks_list:
                plot_disks[disk]=color_list[index]
                index=index+1

            print (plot_disks)

            for k,v in plot_disks.items():
                
                disk_data=all_node_data[k][2]
                item_time=all_node_data[k][0]
                plot_time=convert_time_to_matplot(item_time)

                ax_arr[i].plot(plot_time,disk_data, color=v,linewidth=2,label=k)
                ax_arr[i].xaxis_date()
                ax_arr[i].xaxis.set_major_formatter(xfmt)


            i=i+1     
        except Exception as e:
            logging.info("catch exception:{}".format(str(e)))
            logging.info("call trace:{}".format(traceback.format_exc()))


    plt.tight_layout()
    plt.show()





    
def plot_data(plot_time):

    fig, ax = plt.subplots()

    ax.plot(fds, read_ops, 'ro-')
    ax.xaxis_date()
    fig.autofmt_xdate()
    xfmt = mdate.DateFormatter('%y-%m-%d %H:%M')
    ax.xaxis.set_major_formatter(xfmt)
    
    plt.show()

def convert_time_to_matplot(item_time):

    begin_time=item_time[0]
    end_time=item_time[1]
    delta_time=item_time[2]
    #print (begin_time,end_time,delta_time)
    time_list=[]
    time_list.append(begin_time)
    next_time = begin_time + delta_time
    while next_time < end_time:
        time_list.append(next_time)
        next_time = next_time + delta_time
    #print(time_list)
    #print(len(time_list))
    
    #plot_time=mdate.num2date(time_list)
    
    datetime_list = map(datetime.datetime.fromtimestamp, time_list)
    
    plot_time = mdate.date2num(datetime_list) 
    return plot_time


def process_host_cpu_data(filename):

    with open(filename,'r') as f:
        data = json.load(f)
    



def main(argv=None):
    print('begin')
    
    #fig, ax = plt.subplots()
    #process_cluster_data('cluster.collect_data',fig,ax)
    nodes=['192.168.123.127','192.168.123.128','192.168.123.141','192.168.123.142','192.168.123.143']
    #process_cluster_data('cluster.collect_data')
    process_all_node_disk_util('host_disk_util.collect_data',nodes)

if __name__ == "__main__":
    sys.exit(main())


