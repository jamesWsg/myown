#!/usr/bin/env/python
#------------------------------------------------------------
# @author: wangpeng
# @email:  peng_wang@bigtera.com.cn
# @date:   2017/02/15
# @brief:  it's used to create raid
#------------------------------------------------------------
from __future__ import print_function
import sys
import os
import re
import time
import copy
import logging
import ConfigParser
from optparse import OptionParser
from ezs3.command import do_cmd
from ezs3.log import EZLog, SysLogFile, enable_debug_log
sys.path.append('/usr/lib/cgi-bin/ezs3')

MEGACLI="/opt/MegaRAID/MegaCli/MegaCli64"

EZLog.init_handler(logging.DEBUG, "/var/log/ezcloudstor/do_raid.log")
logger = EZLog.get_logger("do_raid")
g_dbg_pd = "Enclosure Device ID: 32\n" \
             "Slot Number: 0\n" \
             "Media Type:Hard Disk Device\n" \
             "Enclosure Device ID: 32\n" \
             "Slot Number: 1\n" \
             "Media Type: Hard Disk Device\n" \
             "Enclosure Device ID: 32\n" \
             "Slot Number: 2\n" \
              "Media Type: Hard Disk Device\n" \

g_dbg_vd=""

#mycmd = '/opt/MegaRAID/MegaCli/MegaCli64 CfgLDAdd PDList -A0 | grep "Enclosure Device ID|Slot Number|Media Type"'
#-----------------------------------------------------------------------------
class CDefaults:
    RAID0_DISK_MINIMUM = 1
    RAID1_DISK_MINIMUM = 2
    RAID5_DISK_MINIMUM = 3
    RAID5_DISK_MAXIMUM = 20
    SATA_DISK = "Hard Disk Device"
    ENCLOSURE_DEV_ID = "Enclosure Device ID"
    SLOT_NO = "Slot Number"
    MEDIA_TYPE = "Media Type"

class CRaid:

    def __init__(self, cfg_path):

        self.osd_raid_level = -1
        self.osd_disk_num = -1
        self.is_disk_remain_use = 0
        self.ssd_raid_level = -1
        self.ssd_disk_num = -1
        self.conf_file = cfg_path

        self.disk_attr = [CDefaults.ENCLOSURE_DEV_ID, CDefaults.SLOT_NO, CDefaults.MEDIA_TYPE]
        self.disk_list = {'pd_list':self.get_pd_list, 'vd_list':self.get_vd_list, 'valid_list':self.get_valid_pd_list}
        self.do_raid = {0:self._raid0, 1:self._raid1, 5:self._raid5}


    def _raid_t(self, disk_list, raid_disk_num, raid_level):
        """
        total:  the number all of disk
        remain: the number of remain disk  is not enougth to make a raid 
        make_raid: the number of disk list to make raid
        group: the number of raid can make
        """
        total = len(disk_list)
        remain = total % raid_disk_num
        make_raid = total - remain

        for i in range(0, make_raid, raid_disk_num):
            raid = ''
            for j in range(0, raid_disk_num):
                e_id = disk_list[i+j][CDefaults.ENCLOSURE_DEV_ID]
                s_no = disk_list[i+j][CDefaults.SLOT_NO]
                item = "{}:{},".format(e_id, s_no)
                raid = raid + item

            raid = raid[:-1]
            cmd = "/opt/MegaRAID/MegaCli/MegaCli64 CfgLDAdd -r{} [{}] -A0".format(raid_level, raid)
            print("I will create RAID : {}".format(cmd))
            do_cmd(cmd)

    def _raid0(self, disk_list, raid_disk_num):
        self. _raid_t(disk_list, raid_disk_num, 0)


    def _raid1(self, disk_list, raid_disk_num):
        self._raid_t(disk_list, raid_disk_num, 1)


    def _raid5(self, disk_list, raid_disk_num):
        self._raid_t(disk_list, raid_disk_num, 5)
    

    def raid_level(self):
        return self.osd_raid_level


    def raid_disk_num(self) :
        return self.osd_disk_num


    # parser cfg.ini and check field validity
    def is_cfg_ok(self):
        # init parser
        cfg = ConfigParser.ConfigParser()
        cfg.read(self.conf_file)

        # parser field
        self.osd_raid_level = cfg.get("sec_osd_raid", "raid_level")
        self.osd_disk_num = cfg.get("sec_osd_raid", "disk_num")
        self.is_disk_remain_use = cfg.get("sec_osd_raid", "is_disk_remain_use")
        self.ssd_raid_level = cfg.get("sec_ssd_raid", "raid_level")
        self.ssd_disk_num = cfg.get("sec_ssd_raid", "disk_num")
        dbg = "osd_raid_level={}|osd_disk_num={}|is_disk_remain_use={}|ssd_raid_level={}|ssd_disk_num={}" \
               .format(self.osd_raid_level, self.osd_disk_num, self.is_disk_remain_use, self.ssd_raid_level, self.ssd_disk_num)
        print(dbg)
        logger.debug(dbg)
        
         # raid0 = 1 disk
        if (0 == self.osd_raid_level) \
            and (CDefaults.RAID0_DISK_MINIMUM != self.osd_disk_num):
            return False
        # raid1 = 2 disk
        if (1 == self.osd_raid_level) \
            and (defaults.RAID1_DISK_MINIMUM != self.osd_disk_num):
            return False
        # raid5 > 3 disk
        if (5 == self.osd_raid_level) \
            and (defaults.RAID5_DISK_MINIMUM > osd_disk_num \
                and defaults.RAID5_DISK_MAXIMUM < osd_disk_num):
            return False

        return True

    def get_pd_list(self, str_pd_list):

        disk_item = {}
        disk_list = []

        attr_sz = len(self.disk_attr)
        ecls = self.disk_attr[0]
        slot = self.disk_attr[1]

        line_no = 1
        for line in str_pd_list.splitlines():
            pair = line.split(':')
            # string 2 int
            pair[0] = pair[0].strip()
            pair[1] = pair[1].strip()
            if (pair[0] == ecls) or (pair[0] == slot):
                pair[1] = int(pair[1])

            # load disk attribute 2 my dictionary
            disk_item.update({pair[0] : pair[1]})
            if (line_no % attr_sz) == 0:
                if pair[1] == CDefaults.SATA_DISK:
                    disk_list.append(copy.deepcopy(disk_item))
                disk_item.clear()

            line_no = line_no + 1

        return disk_list

    def get_vd_list(self, str_vd_list):

        disk_item = {}
        disk_list = []

        #cmd = "/opt/MegaRAID/MegaCli/MegaCli64 LDPDinfo -Lall -A0 | grep -Ei {}".format(disk_attrs)
        attr_sz = len(self.disk_attr)
        ecls = self.disk_attr[0]
        slot = self.disk_attr[1]

        line_no = 1
        for line in str_vd_list.splitlines():
            pair = line.split(':')
            if (pair[0] == ecls) or (pair[0] == slot):
                pair[1] = int(pair[1])

            disk_item.update({pair[0] : pair[1]})
            if (line_no % attr_sz) == 0:
                if pair[1] == CDefaults.SATA_DISK:
                    disk_list.append(copy.deepcopy(disk_item))
                disk_item.clear()
            line_no = line_no + 1

        return disk_list

    def get_valid_pd_list(self, pd_list, vd_list):
        # filter(remove) vdlist from pdlist
        # return if the remaining disks can do not a raid, or continue
        # select the disks in minimum distance to do raid
        # process the remaining disk when raid is finish.
        for vd in vd_list:
            if vd in pd_list:
                pd_list.remove(vd)

        return pd_list
        

def main(argv=None):
    if argv == None:
        argv = sys.argv
  

    usage = "Usage: %prog [options]"
    parser = OptionParser(usage=usage)
    parser.add_option(
        "-f", "--conf", dest="conf",
        help="config file for program"
    )
    
    (options, args) = parser.parse_args()
    
    if options.conf is None:
        print("config file is not exists",file=sys.stderr)
        return 1

    oraid = CRaid(options.conf)
    if not oraid.is_cfg_ok():
        sys.exit(1)

    f_pd_list = oraid.disk_list['pd_list']
    f_vd_list = oraid.disk_list['vd_list']
    f_valid_list = oraid.disk_list['valid_list']

    pdlist_cmd_str = "{} -PDList -A0 |grep  -Ei 'Enclosure Device|Slot Number|Media Type'".format(MEGACLI)
    pdlist_out = do_cmd(pdlist_cmd_str, force=True) 

    ldpdinfo_cmd = "{} -LDPDinfo -A0 |grep -Ei 'Enclosure Device|Slot Number|Media Type'".format(MEGACLI)
    ldpdinfo_out = do_cmd(ldpdinfo_cmd, force=True)


    pd_list = f_pd_list(pdlist_out)
    vd_list = f_vd_list(ldpdinfo_out)
    valid_list = f_valid_list(pd_list, vd_list)

    raid_level = oraid.raid_level()
    raid_disk_num = oraid.raid_disk_num()
    f_do_raid = oraid.do_raid[int(raid_level)]
    f_do_raid(valid_list, int(raid_disk_num))
    
    sorted(valid_list)
#    print valid_list

    sys.exit(0)


if __name__ == "__main__":
    sys.exit(main())


