#!/bin/sh

mkdir -p /root/import_log_2_es

cp -f ./import_radosgw_access_log_to_es.py /usr/local/bin/import_radosgw_access_log_to_es.py
cp -f ./import_radosgw_access_log_to_es.conf /etc/ezs3/import_radosgw_access_log_to_es.conf
cp -f ./import_access_log  /etc/cron.d/

echo "Installation finished."
