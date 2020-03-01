
#!/bin/bash

zabbix_serer=172.17.73.69
agent_ip=`ip add |grep 172.17 |awk '{print $2}' |head -n 1 |awk -F/ '{print $1}'`

host_name=`hostname`
agent_name=${host_name}_${agent_ip}

#sed -i "s/^Server=127.0.0.1/Server=${zabbix_serer}/g" /etc/zabbix/zabbix_agentd.conf 

## consider the zabbix server is a docker,use active mode of zabbix-agent,the above is passive mode
#ServerActive=127.0.0.1
sed -i "s/^ServerActive=127.0.0.1/ServerActive=${zabbix_serer}/g" /etc/zabbix/zabbix_agentd.conf


sed -i "s/^Hostname=Zabbix server/Hostname=${agent_name}/g" /etc/zabbix/zabbix_agentd.conf


