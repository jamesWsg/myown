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

#EZLog.init_handler(logging.INFO, "report.log")
#logger = EZLog.get_logger("report")

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
    #debug print(read_ops)
    for item_data in all_item_data:
        read_ops.append(item_data[0])
        write_ops.append(item_data[1])
        read_bytes.append(item_data[2])
        write_bytes.append(item_data[3])
    '''
    plot
    '''
    #debug print(read_bytes)
    # debug print(read_ops)

    fig, ax_arr = plt.subplots(2,sharex=True)

    #ax.plot(fds, read_ops, 'ro-')
    ax_arr[0].plot(plot_time, read_ops, 'palegreen',label='read')
    ax_arr[0].plot(plot_time, write_ops, 'black',label='write')

    ax_arr[0].xaxis_date()
    #fig.autofmt_xdate()
    xfmt = mdate.DateFormatter('%y-%m-%d %H:%M')
    ax_arr[0].xaxis.set_major_formatter(xfmt)
    
    ax_arr[0].set_xlabel('date')
    ax_arr[0].set_ylabel('iops',fontsize=8)
    ax_arr[0].legend(loc='best', fontsize=6,ncol=4)

    ax_arr[0].set_title('cluster IOPS')
    ##

    read_MB=[]
    write_MB=[]
    for each in read_bytes:
        if each == None:
            result= None
            read_MB.append(result)
        else:
            result=each/1024/1024
            read_MB.append(result)

    for each in write_bytes:
        if each == None:
            result= None
            write_MB.append(result)
        else:
            result=each/1024/1024
            write_MB.append(result)

    print ('read MB \n {}'.format(read_MB))

    ax_arr[1].plot(plot_time, read_MB, 'palegreen',label='read')
    ax_arr[1].plot(plot_time, write_MB, 'black',label='write')

    ax_arr[1].xaxis_date()
    ax_arr[1].xaxis.set_major_formatter(xfmt)
    
    ax_arr[1].set_xlabel('date')
    ax_arr[1].set_ylabel('MB',fontsize=8)
    ax_arr[1].legend(loc='best', fontsize=6,ncol=4)
    
    ax_arr[1].set_title('cluster throughput')
    #plt.show()

    plt.tight_layout()
    plt.savefig('cluster')
    plt.close('all')






def process_all_node_network(filename,nodes):
    print('begin process network data')
    with open(filename,'r') as f:
        data = json.load(f)
    print('open rrd_data')
    all_node_data=data['data']

    plot_num=len(nodes)
    fig, ax_arr = plt.subplots(plot_num,sharex=True)
    
    xfmt = mdate.DateFormatter('%y-%m-%d %H:%M')
    
    print(plot_num)

    i=0
    # i is for plt.subplot
    for node in nodes:
        try:
            storage_interface=all_node_eth_info[node]['storage_interface']
            public_interface=all_node_eth_info[node]['public_interface']


            node_data_storage_interface='node.{}.{}'.format(node,storage_interface)
            node_data_public_interface='node.{}.{}'.format(node,public_interface)
            item_time=all_node_data[node_data_storage_interface][0]

            plot_time=convert_time_to_matplot(item_time)

            node_data_storage_interface_util=all_node_data[node_data_storage_interface][2]
            node_data_public_interface_util=all_node_data[node_data_public_interface][2]
            '''
            plot
            '''
            #debug print('i:{}\n'.format(i))
            #debug print(node_data_storage_interface_util)
            #ax.plot(fds, read_ops, 'ro-')
            ax_arr[i].plot(plot_time, node_data_storage_interface_util, color='black',linewidth=2,label='storage_interface_util')
            ax_arr[i].plot(plot_time, node_data_public_interface_util, color='green',linewidth=2,linestyle=':',label='public_interface_util')

            ax_arr[i].xaxis_date()
            #fig.autofmt_xdate()
            ax_arr[i].xaxis.set_major_formatter(xfmt)
            #ax_arr[i].set_xlabel('date')
            ax_arr[i].set_ylabel('util',fontsize=8)
            ax_arr[i].set_yticks([0, 0.2, 0.4, 0.6, 0.8,1.0])

            ax_title='node {} network util'.format(node)
            ax_arr[i].set_title(ax_title)
            #ax_arr[i].legend(loc='lower center', bbox_to_anchor=(0.5, -0.7),fontsize=6,ncol=8, shadow=True, fancybox=True)
            ax_arr[i].legend(loc='upper right',fontsize=6,ncol=8)
            i=i+1

        except Exception as e:
            logger.error("catch exception:{}".format(str(e)))
            logger.error("call trace:{}".format(traceback.format_exc()))

    plt.tight_layout()
    plt.rcParams.update({'font.size': 8})
    #plt.show()
    #plt.legend(loc='lower center', ncol=2, shadow=True, fancybox=True)
    plt.savefig('allnode_network_util',dpi=400)
    #plt.show()
    plt.close('all')

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


    # debug print(plot_num)

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

            # debug print (plot_disks)

            for k,v in plot_disks.items():
                
                disk_data=all_node_data[k][2]
                item_time=all_node_data[k][0]
                plot_time=convert_time_to_matplot(item_time)
                disk_name=k.split('.')[-1]


                ax_arr[i].plot(plot_time,disk_data, color=v,label=disk_name)

            ax_arr[i].xaxis_date()
            ax_arr[i].xaxis.set_major_formatter(xfmt)

            #ax_arr[i].set_xlabel('date')
            ax_arr[i].set_ylabel('util %',fontsize=10)
            ax_arr[i].set_yticks([0, 20, 40, 60, 80,100])

            ax_title='node {} disk util'.format(node)
            ax_arr[i].set_title(ax_title)
            #ax_arr[i].legend(loc='lower right', bbox_to_anchor=(1, -0.4),fontsize=6,ncol=8, shadow=True, fancybox=True)
            ax_arr[i].legend(loc='upper right',fontsize=6,ncol=8)

            i=i+1     
        except Exception as e:
            logging.info("catch exception:{}".format(str(e)))
            logging.info("call trace:{}".format(traceback.format_exc()))


    plt.tight_layout()
    plt.rcParams.update({'font.size': 8})
    plt.savefig('allnode_disk_util',dpi=400)
    #plt.show()


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
    

def parse_ctdb(ctdb_result):
    result=''
    # assume the content is ## head 2 in markdown report

    if 'Bad' in ctdb_result.keys():
        result ='## some bad\n'
    else:
        ctdb_markdown='## ctdb 运行状态\n'
        table='|节点IP|ctdb 状态|\n| ------ | ----- |\n'
        for each_item in ctdb_result['OK_part']:
            row='|{}|{}|\n'.format(each_item['IP'],each_item['status'])
            table=table+row
        
        ctdb_markdown=ctdb_markdown+table

    result=result+ctdb_markdown
    return result


def parse_mds(mds_result):
    result=''
    # assume the content is ## head 2 in markdown report

    if 'Bad' in mds_result.keys():
        result ='## some bad\n'
    else:
        mds_markdown='## mds 运行状态\n'
        table='|节点IP|mds 状态|\n| ------ | ----- |\n'
        for each_item in mds_result['OK_part']:
            row='|{}|{}|\n'.format(each_item['IP'],each_item['status'])
            table=table+row
        
        mds_markdown=mds_markdown+table

    result=result+mds_markdown
    return result
    
def parse_High_Mem_Process(process_result):
    result=''
    # assume the content is ## head 2 in markdown report

    if 'Bad' in process_result.keys():
        result ='## some bad\n'
    else:
        process_markdown='## 各个节点内存消耗最多的进程\n'
        #table='|节点IP|进程名|当前占用内存(MB)|申请内存(MB)|\n| ------ | ----- |\n'
        table='|节点IP|进程名以及占用内存|\n| ------ | ----- |\n'
        for each_item in process_result['OK_part']:
            # detail info is a list，can not use by each_item['detail_info']['rss']
            row='|{}|{}|\n'.format(each_item['IP'],each_item['detail_info'])
            table=table+row
        
        process_markdown=process_markdown+table

    result=result+process_markdown
    return result

def parse_OS_partion_usage(process_result):
    result=''
    # assume the content is ## head 2 in markdown report

    if 'Bad' in process_result.keys():
        result ='## some bad\n'
    else:
        process_markdown='## 各个节点系统盘的使用率\n'
        table='|节点IP|系统盘使用率(%)|\n| ------ | ----- |\n'
        for each_item in process_result['OK_part']:
            # detail info is a list，can not use by each_item['detail_info']['rss']
            row='|{}|{}|\n'.format(each_item['IP'],each_item['used_pecent'])
            table=table+row
        
        process_markdown=process_markdown+table

    result=result+process_markdown
    return result
def parse_ssd_duration(process_result):
    result=''
    # assume the content is ## head 2 in markdown report

    if 'Bad' in process_result.keys():
        result ='## some bad\n'
    else:
        process_markdown='## 各个节点的进程数目\n'
        table='|节点IP|寿命需要注意的SSD|寿命正常的SSD|\n| ------ | ----- |----- |\n'
        for each_item in process_result['OK_part']:
            # detail info is a list，can not use by each_item['detail_info']['rss']
            row='|{}|{}|{}|\n'.format(each_item['IP'],each_item['elder_ssds'],each_item['young_ssds'])
            table=table+row
        
        process_markdown=process_markdown+table

    result=result+process_markdown
    return result
def parse_process_number(process_result):
    result=''
    # assume the content is ## head 2 in markdown report

    if 'Bad' in process_result.keys():
        result ='## some bad\n'
    else:
        process_markdown='## 各个节点的进程数目\n'
        table='|节点IP|进程数目|\n| ------ | ----- |\n'
        for each_item in process_result['OK_part']:
            # detail info is a list，can not use by each_item['detail_info']['rss']
            row='|{}|{}|\n'.format(each_item['IP'],each_item['process_num'])
            table=table+row
        
        process_markdown=process_markdown+table

    result=result+process_markdown
    return result
def parse_EXT4_erro(process_result):
    result=''
    # assume the content is ## head 2 in markdown report

    if 'Bad' in process_result.keys():
        result ='## some bad\n'
    else:
        process_markdown='## 各个节点的EXT4状态\n'
        table='|节点IP|EXT4状态|\n| ------ | ----- |\n'
        for each_item in process_result['OK_part']:
            # detail info is a list，can not use by each_item['detail_info']['rss']
            row='|{}|无EXT4错误|\n'.format(each_item['IP'])
            table=table+row
        
        process_markdown=process_markdown+table

    result=result+process_markdown
    return result
def parse_checklist(process_result):
    print('begin generate checklist info')
    result=''
    process_markdown='检查项目列表如下\n'
    table='|检查项|检查函数|\n| ------ | ----- |\n'
    for each_item in process_result.keys():
        row='|检查项|{}|\n'.format(each_item)
        table=table+row
    
    process_markdown=process_markdown+table

    result=result+process_markdown
    return result

def parse_load_average(process_result):
    print('begin generate load average')
    result=''
    # assume the content is ## head 2 in markdown report

    if 'Bad' in process_result.keys():
        result ='## some bad\n'
    else:
        process_markdown='## 各个节点cpu的负载情况\n'
        table='|节点IP|1分钟cpu负载|5分钟cpu负载|15分钟cpu负载|\n| ------ | ----- | ----- | ----- |\n'
        for each_item in process_result['OK_part']:
            row='|{}|{}|{}|{}|\n'.format(each_item['IP'],each_item['load_1_minute'],each_item['load_5_minute'],each_item['load_15_minute'])
            table=table+row
        
        process_markdown=process_markdown+table

    result=result+process_markdown
    return result
def parse_free_memory(process_result):
    result=''
    # assume the content is ## head 2 in markdown report

    if 'Bad' in process_result.keys():
        result ='## some bad\n'
    else:
        process_markdown='## 各个节点内存使用情况\n'
        table='|节点IP|总内存|可用内存|\n| ------ | ----- | ----- |\n'
        for each_item in process_result['OK_part']:
            row='|{}|{}|{}|\n'.format(each_item['IP'],each_item['total_mem'],each_item['free_mem'])
            table=table+row
        
        process_markdown=process_markdown+table

    result=result+process_markdown
    return result
def parse_cluster_info(cluster_check_result):
    #now not process the bad part
    result={}

    cluster_result='## 集群检查情况\n'
    table='|检查项|检查结果|\n| ------ | ----- |\n'

    # ceph health result ok_part if diff from other,bean's fault,and the result have the \n

    ceph_health_result=cluster_check_result['Ceph Health']['ok_part']['cluster_status']

    table=table + '|ceph health|{}|\n'.format(ceph_health_result[:-1])
    table=table + '|集群容量使用|{}|\n'.format(cluster_check_result['Cluster Cacacity']['OK_part']['cluster_usage'])
    table=table+'|osd down|{}|\n'.format(cluster_check_result['OSD down']['ok_part']['result'])
    table=table+'|osd failed|{}|\n'.format(cluster_check_result['OSD failed']['ok_part']['result'])
    table=table+'|mon 选举|{}|\n'.format(cluster_check_result['Mon leader changed']['ok_part']['result'])

    result=cluster_result + table
    return result



def generate_markdown(cluster_check_result):
    
    result = {}

    title='#                    **bigtera存储巡检报告**\n'

    h1_summary='# 巡检结果\n集群状态正常，运行稳定,过去一段时间的运行情况详见如下：包括集群的带宽和iops，各个节点的网络使用情况、磁盘使用情况等\n'
    summary_chart_cluster ='## 集群在过去30天内的带宽和iops情况如下\n![]({})\n'.format('cluster.png')
    summary_chart_all_node_network_util='## 集群每个节点的存储业务网和存储内网的网络使用率\n![]({})\n'.format('allnode_network_util.png')
    summary_chart_all_node_disk_util='## 集群每个节点的磁盘使用率\n![]({})\n'.format('allnode_disk_util.png')
    h1_summary=title+h1_summary+summary_chart_cluster+summary_chart_all_node_network_util+summary_chart_all_node_disk_util




    h1_checklist='# 本次巡检的检查项如下表，每个检查项的详细结果附在表后\n'
    checklist_info=parse_checklist(cluster_check_result)
    h1_checklist=h1_checklist+checklist_info


    ctdb_info=parse_ctdb(cluster_check_result['CTDB Status'])
    cluster_info=parse_cluster_info(cluster_check_result)
    mds_info=parse_mds(cluster_check_result['MDS Status'])
    high_mem_process_info=parse_High_Mem_Process(cluster_check_result['High-Mem Process'])
    load_average_info=parse_load_average(cluster_check_result['Load Average'])
    process_number_info=parse_process_number(cluster_check_result['Process Number'])
    free_mem_info=parse_free_memory(cluster_check_result['Free Memory'])
    OS_partion_info=parse_OS_partion_usage(cluster_check_result['OS Partition Usage'])
    EXT4_erro_info=parse_EXT4_erro(cluster_check_result['EXT4-fs error'])
    SSD_duration_info=parse_ssd_duration(cluster_check_result['SSD Duration'])

    output=cluster_info+mds_info+ctdb_info+high_mem_process_info+load_average_info+process_number_info+free_mem_info+OS_partion_info+SSD_duration_info+EXT4_erro_info


    print (load_average_info)
    with open('report.md','w') as f:
        f.write(h1_summary)
        f.write(h1_checklist)

        f.write(output)

def main(argv=None):
    print('begin')
    
    #fig, ax = plt.subplots()
    #process_cluster_data('cluster.collect_data',fig,ax)

    print('begin read node info')

    with open('all_node_eth_info','r') as f:
        all_node_eth_info = json.load(f)


    nodes=all_node_eth_info.keys()
    process_cluster_data('cluster.collect_data')
    process_all_node_network('host_network_util.collect_data',nodes)
    process_all_node_disk_util('host_disk_util.collect_data',nodes)
    with open('cluster_check.20171024.detail','r') as f:
        data = json.load(f)        
    generate_markdown(data)

if __name__ == "__main__":
    sys.exit(main())


