
########
test find that 
when use qperf ip tcp_bw tcp_lat cost 4ms
when use qperf ip tcp_bw cost 2ms

so two option (tcp_bw,tcp_lat) run together and seperate is the same,

the script is seperate run the two option


#### test ins zabbix-agent
ip can be defined in template macro 

root@node1:/backups# zabbix_agentd -t qperf[172.17.75.62,bw]
qperf[172.17.75.62,bw]                        [t|90.8]
root@node1:/backups# zabbix_agentd -t qperf[172.17.75.62,lat]
qperf[172.17.75.62,lat]                       [t|216]
root@node1:/backups# 
