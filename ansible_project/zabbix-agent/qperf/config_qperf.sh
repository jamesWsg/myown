#!/bin/bash
PWD=`pwd`
BIN_DIR='/usr/local/zabbix-agent-ops/bin'

### ?? need add cp the qperf bin to /us/local/bin
cp ${PWD}/qperf/qperf_check.sh ${BIN_DIR}/

cp ${PWD}/qperf/qperf-param.conf /etc/zabbix/zabbix_agentd.d/
