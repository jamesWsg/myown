#!/bin/bash

PWD=`pwd`
BIN_DIR='/usr/local/zabbix-agent-ops/bin'
TMP_DATA_DIR='/usr/local/zabbix-agent-ops/var'

mkdir -p ${BIN_DIR}
mkdir -p ${TMP_DATA_DIR}

## cp cronjob and corresbonding shell
cp ${PWD}/iostat/iostat_cron_conf /etc/cron.d


##cp shell to BIN_DIR
cp ${PWD}/iostat/*.sh ${BIN_DIR}/


##cp zabbix agent conf
cp ${PWD}/iostat/iostat-params.conf /etc/zabbix/zabbix_agentd.d/


