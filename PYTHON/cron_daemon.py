#!/usr/bin/env python

## should put this file in /usr/local/bin/ ,and grant excute permission, and add cron in /etc/cron.d/ as following
## 0 02 * * 6  root python /usr/local/bin/cron_daemon.py >/dev/null 2>&1

import logging
import commands


logging.basicConfig(filename='/var/log/ezcloudstor/cron_daemon.log',format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S',level=logging.INFO)
logging.info('log begin.')

def check_daemon(daemon_name):
   # first check the curent status
   output=commands.getoutput("ps aux |grep {}".format(daemon_name))
   logging.info('the curent status of {}:\n{}'.format(daemon_name,output))

   #begin stop,need attention,bind to the daemon name, 
   output=commands.getoutput("/etc/init.d/{} stop".format(daemon_name))
   logging.info('the stop  status of {}:\n{}'.format(daemon_name,output))

   # check stop restult
   output=commands.getoutput("ps aux |grep {}".format(daemon_name))
   logging.info('the stop result of {}:\n{}'.format(daemon_name,output))

def check_daemon_exist(daemon_name):
    result=''
    output=commands.getoutput("ls /var/run/*.pid").split("\n")
    ##debug print "daemon list :{}".format(output)
    ##debug print output
    for each_line in output:
        #debug print "each_line:{}".format(each_line)
        if daemon_name in each_line:
            # debug print "hit daemon_name:{}".format(each_line)
            result= True
        else:
             result=False
    return result


if __name__ == '__main__':

    daemon_list=['ezmonitor','ezqos']

    for daemon in daemon_list:
        check_daemon(daemon)

    ## boot the daemon only the daemon not exist,if exist,do not boot
    for daemon_name in daemon_list:
        if check_daemon_exist(daemon_name):
            logging.error('the daemon {} is still exist,so i do not boot again, the stop did not take effect \n'.format(daemon_name))

        else:
            output=commands.getoutput("/etc/init.d/{} start".format(daemon_name))
            logging.info('the start  status of {}:\n{}'.format(daemon_name,output)) 

            output=commands.getoutput("ps aux |grep {}".format(daemon_name))
            logging.info('the start result of {}:\n{}'.format(daemon_name,output))





